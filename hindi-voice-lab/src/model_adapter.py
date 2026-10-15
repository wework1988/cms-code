"""Chatterbox Multilingual loader.

The pinned package is chatterbox-tts 0.1.7. In that release,
ChatterboxMultilingualTTS.from_pretrained(device) downloads
ResembleAI/chatterbox and from_local() loads t3_mtl23ls_v2.safetensors by
filename. There is no t3_model argument and no seed argument. GitHub master
later added an optional t3_model="v3" switch; this lab does not call it.
"""

from __future__ import annotations

import gc
import hashlib
import importlib.metadata
import inspect
import json
import os
import threading
from dataclasses import dataclass
from pathlib import Path

from .config import (
    CACHE,
    CHECKPOINT_FILES,
    LANGUAGE_ID,
    MODELS,
    PACKAGE_NAME,
    PACKAGE_VERSION,
    REPO_ID,
    T3_FILENAME,
    T3_SHA256,
    configure_runtime,
)

_LOCK = threading.Lock()


class ModelError(RuntimeError):
    """The multilingual model cannot be loaded or used."""


@dataclass
class GeneratedChunk:
    samples: list[float]
    sample_rate: int
    device_used: str
    note: str | None = None


class ModelService:
    def __init__(self) -> None:
        self._model = None
        self._loaded_device: str | None = None
        self._cpu_fallback_note: str | None = None

    def status(self) -> dict:
        present = checkpoints_present()
        return {
            "package": f"{PACKAGE_NAME}=={PACKAGE_VERSION}",
            "repo_id": REPO_ID,
            "checkpoint": T3_FILENAME,
            "checkpoint_sha256": T3_SHA256,
            "language_id": LANGUAGE_ID,
            "weights_present": present,
            "loaded": self._model is not None,
            "loaded_device": self._loaded_device,
            "offline": os.environ.get("HF_HUB_OFFLINE") == "1",
        }

    def download(self) -> dict:
        configure_runtime(offline=False)
        try:
            from huggingface_hub import snapshot_download
        except Exception as exc:
            raise ModelError(
                "huggingface_hub is not installed. Run scripts/setup.sh in hindi-voice-lab first."
            ) from exc
        try:
            snapshot = Path(
                snapshot_download(
                    repo_id=REPO_ID,
                    repo_type="model",
                    revision="main",
                    allow_patterns=list(CHECKPOINT_FILES),
                )
            )
        except Exception as exc:
            raise ModelError(self._download_error(exc)) from exc
        digest = _sha256(snapshot / T3_FILENAME)
        if digest != T3_SHA256:
            raise ModelError(
                f"Refusing to use {T3_FILENAME}: sha256 is {digest}, expected {T3_SHA256}. "
                "The Hugging Face main revision no longer matches the file this package loads."
            )
        manifest = {
            "package": f"{PACKAGE_NAME}=={PACKAGE_VERSION}",
            "repo_id": REPO_ID,
            "revision": "main",
            "snapshot_dir": str(snapshot),
            "t3_filename": T3_FILENAME,
            "t3_sha256": digest,
            "files": list(CHECKPOINT_FILES),
            "language_id": LANGUAGE_ID,
        }
        destination = MODELS / "manifest.json"
        temporary = destination.with_suffix(".json.tmp")
        temporary.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
        os.replace(temporary, destination)
        return manifest

    def generate(
        self,
        text: str,
        reference_wav: Path,
        device: str,
        exaggeration: float,
        cfg_weight: float,
        temperature: float,
        repetition_penalty: float,
        min_p: float,
        top_p: float,
        seed: int | None,
        offline: bool,
    ) -> GeneratedChunk:
        with _LOCK:
            note = self._ensure_loaded(device, offline)
            try:
                return self._generate_on_loaded_model(
                    text,
                    reference_wav,
                    exaggeration,
                    cfg_weight,
                    temperature,
                    repetition_penalty,
                    min_p,
                    top_p,
                    seed,
                    note,
                )
            except ModelError:
                raise
            except Exception as exc:
                if _is_oom(exc):
                    raise ModelError(_oom_message(self._loaded_device or device)) from exc
                if (self._loaded_device == "mps") and _is_mps_failure(exc):
                    reason = str(exc).strip() or exc.__class__.__name__
                    self._drop_model()
                    fallback = (
                        f"MPS failed with an unsupported operation: {reason} "
                        "Retried this generation on CPU. Acceleration is not in use."
                    )
                    self._cpu_fallback_note = fallback
                    self._ensure_loaded("cpu", offline)
                    try:
                        return self._generate_on_loaded_model(
                            text,
                            reference_wav,
                            exaggeration,
                            cfg_weight,
                            temperature,
                            repetition_penalty,
                            min_p,
                            top_p,
                            seed,
                            fallback,
                        )
                    except Exception as retry_exc:
                        if _is_oom(retry_exc):
                            raise ModelError(_oom_message("cpu")) from retry_exc
                        raise ModelError(f"CPU retry also failed: {retry_exc}") from retry_exc
                raise ModelError(f"Generation failed: {exc}") from exc

    def _generate_on_loaded_model(
        self,
        text: str,
        reference_wav: Path,
        exaggeration: float,
        cfg_weight: float,
        temperature: float,
        repetition_penalty: float,
        min_p: float,
        top_p: float,
        seed: int | None,
        note: str | None,
    ) -> GeneratedChunk:
        import torch

        model = self._model
        if model is None or self._loaded_device is None:
            raise ModelError("The model is not loaded.")
        _seed_torch(torch, seed)
        signature = inspect.signature(model.generate)
        supported = set(signature.parameters)
        required = {"text", "language_id", "audio_prompt_path", "exaggeration", "cfg_weight", "temperature"}
        missing = required - supported
        if missing:
            raise ModelError(
                "The installed generate() method is missing "
                f"{sorted(missing)}. Expected chatterbox-tts {PACKAGE_VERSION}."
            )
        kwargs = {
            "language_id": LANGUAGE_ID,
            "audio_prompt_path": str(reference_wav),
            "exaggeration": exaggeration,
            "cfg_weight": cfg_weight,
            "temperature": temperature,
        }
        if "repetition_penalty" in supported:
            kwargs["repetition_penalty"] = repetition_penalty
        if "min_p" in supported:
            kwargs["min_p"] = min_p
        if "top_p" in supported:
            kwargs["top_p"] = top_p
        if "seed" in supported:
            raise ModelError(
                "This installed generate() accepts seed, which chatterbox-tts "
                f"{PACKAGE_VERSION} does not. Reinstall the pinned requirements."
            )
        wav = model.generate(text, **kwargs)
        array = wav.detach().cpu().float().numpy().reshape(-1)
        return GeneratedChunk(
            samples=array.tolist(),
            sample_rate=int(model.sr),
            device_used=self._loaded_device,
            note=note,
        )

    def _ensure_loaded(self, device: str, offline: bool) -> str | None:
        configure_runtime(offline=offline)
        resolved = resolve_device(device)
        note = None
        if resolved == "mps" and device == "auto" and self._cpu_fallback_note:
            resolved = "cpu"
            note = self._cpu_fallback_note
        if self._model is not None and self._loaded_device == resolved:
            return None
        self._drop_model()
        if offline and not checkpoints_present():
            raise ModelError(
                "Offline mode is on, and the multilingual checkpoint is not in "
                "hindi-voice-lab/cache. Connect once and run scripts/download_models.py."
            )
        cls = _load_class()
        try:
            self._model = cls.from_pretrained(resolved)
        except Exception as exc:
            self._model = None
            self._loaded_device = None
            if _is_oom(exc):
                raise ModelError(_oom_message(resolved)) from exc
            if resolved == "mps" and _is_mps_failure(exc):
                reason = str(exc).strip() or exc.__class__.__name__
                self._model = cls.from_pretrained("cpu")
                self._loaded_device = "cpu"
                note = (
                    f"MPS could not load the model ({reason}). "
                    "Loaded on CPU instead. Acceleration is not in use."
                )
                self._cpu_fallback_note = note
                return note
            if offline:
                raise ModelError(
                    "Offline mode could not open the local checkpoint. "
                    f"Download it while online with scripts/download_models.py. Detail: {exc}"
                ) from exc
            raise ModelError(f"Could not load Chatterbox Multilingual: {exc}") from exc
        self._loaded_device = resolved
        return note

    def _drop_model(self) -> None:
        self._model = None
        self._loaded_device = None
        gc.collect()
        try:
            import torch

            if hasattr(torch, "mps") and hasattr(torch.mps, "empty_cache"):
                torch.mps.empty_cache()
            if torch.cuda.is_available():
                torch.cuda.empty_cache()
        except Exception:
            return

    @staticmethod
    def _download_error(exc: Exception) -> str:
        text = str(exc).strip() or exc.__class__.__name__
        return (
            "Could not download the Chatterbox Multilingual checkpoint. "
            "Check the network connection and try scripts/download_models.py again. "
            f"Detail: {text}"
        )


def resolve_device(requested: str) -> str:
    name = (requested or "auto").strip().lower()
    try:
        import torch
    except Exception as exc:
        raise ModelError(
            "PyTorch is not installed in hindi-voice-lab/.venv. Run scripts/setup.sh."
        ) from exc
    cuda = bool(torch.cuda.is_available())
    mps_built = bool(getattr(torch.backends, "mps", None) and torch.backends.mps.is_built())
    mps_ok = bool(mps_built and torch.backends.mps.is_available())
    if name == "auto":
        if cuda:
            return "cuda"
        if mps_ok:
            return "mps"
        return "cpu"
    if name == "cuda":
        if not cuda:
            raise ModelError("CUDA was requested, but this PyTorch build cannot see a CUDA device.")
        return "cuda"
    if name == "mps":
        if not mps_ok:
            detail = "MPS is not available on this PyTorch build."
            if not mps_built:
                detail = "This PyTorch install was not built with MPS."
            raise ModelError(detail + " Choose CPU, or reinstall the pinned requirements.")
        return "mps"
    if name == "cpu":
        return "cpu"
    raise ModelError("Device must be auto, cuda, mps, or cpu.")


def checkpoints_present() -> bool:
    root = CACHE / "huggingface"
    if not root.exists():
        return False
    needed = set(CHECKPOINT_FILES)
    found: set[str] = set()
    for path in root.rglob("*"):
        if path.name in needed and path.is_file():
            found.add(path.name)
    return needed <= found


def _load_class():
    configure_runtime()
    try:
        installed = importlib.metadata.version(PACKAGE_NAME)
    except importlib.metadata.PackageNotFoundError as exc:
        raise ModelError(
            "chatterbox-tts is not installed. Run scripts/setup.sh inside hindi-voice-lab."
        ) from exc
    if installed != PACKAGE_VERSION:
        raise ModelError(
            f"Found chatterbox-tts {installed}, but this lab is pinned to {PACKAGE_VERSION} "
            "so the checkpoint filename stays t3_mtl23ls_v2.safetensors. "
            "Reinstall hindi-voice-lab/requirements.txt into hindi-voice-lab/.venv."
        )
    from chatterbox.mtl_tts import ChatterboxMultilingualTTS

    signature = inspect.signature(ChatterboxMultilingualTTS.from_pretrained)
    if "t3_model" in signature.parameters:
        raise ModelError(
            "The imported from_pretrained() accepts t3_model, which the pinned "
            f"{PACKAGE_VERSION} package does not. Refusing to guess a checkpoint."
        )
    return ChatterboxMultilingualTTS


def _seed_torch(torch, seed: int | None) -> None:
    if seed is None:
        return
    torch.manual_seed(int(seed))
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(int(seed))
    if hasattr(torch, "mps") and hasattr(torch.mps, "manual_seed"):
        try:
            torch.mps.manual_seed(int(seed))
        except Exception:
            return


def _is_oom(exc: BaseException) -> bool:
    text = str(exc).lower()
    return "out of memory" in text or "not enough memory" in text


def _is_mps_failure(exc: BaseException) -> bool:
    text = str(exc).lower()
    return "mps" in text or "metal" in text or "not implemented" in text


def _oom_message(device: str) -> str:
    return (
        f"The model ran out of memory on {device}. Close other applications, generate a shorter "
        "passage, or set Device to CPU. This Mac shares one memory pool between the system and "
        "the GPU, so a failed MPS allocation does not mean CPU will have the same limit. "
        "The app did not switch devices silently."
    )


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()
