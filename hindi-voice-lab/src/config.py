"""Paths, environment, and runtime cache locations for the voice lab."""

from __future__ import annotations

import logging
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

DATA = ROOT / "data"
REFERENCES = DATA / "references"
PROFILES = DATA / "profiles"
OUTPUTS = DATA / "outputs"
JOBS = DATA / "jobs"
MODELS = ROOT / "models"
CACHE = ROOT / "cache"
TMP = ROOT / "tmp"
LOGS = ROOT / "logs"

HOST = "127.0.0.1"
DEFAULT_PORT = 7865

# chatterbox-tts 0.1.7 from_pretrained() downloads these files from
# ResembleAI/chatterbox and loads t3_mtl23ls_v2.safetensors by name.
# Verified against the published wheel (sha256 83782500e3ad4e7c...).
REPO_ID = "ResembleAI/chatterbox"
PACKAGE_NAME = "chatterbox-tts"
PACKAGE_VERSION = "0.1.7"
T3_FILENAME = "t3_mtl23ls_v2.safetensors"
T3_SHA256 = "b1237586127ce98e7800a68e49938eb5092846862aabcb6e17b2fda7889a6c75"
CHECKPOINT_FILES = (
    "ve.pt",
    T3_FILENAME,
    "s3gen.pt",
    "grapheme_mtl_merged_expanded_v1.json",
    "conds.pt",
    "Cangjie5_TC.json",
)
LANGUAGE_ID = "hi"
MODEL_SAMPLE_RATE = 24000
ENCODER_REFERENCE_SECONDS = 6
DECODER_REFERENCE_SECONDS = 10
MAX_NEW_TOKENS = 1000
TOKEN_RATE_HZ = 25


def load_env_file(path: Path | None = None) -> None:
    """Load KEY=VALUE pairs from .env without overriding existing variables."""
    env_path = path or (ROOT / ".env")
    if not env_path.is_file():
        return
    for raw in env_path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value


def configure_runtime(offline: bool | None = None) -> None:
    """Point library caches at this folder before model libraries are imported."""
    load_env_file()
    for path in (DATA, REFERENCES, PROFILES, OUTPUTS, JOBS, MODELS, CACHE, TMP, LOGS, TMP / "gradio"):
        path.mkdir(parents=True, exist_ok=True)

    hf_home = CACHE / "huggingface"
    os.environ["HF_HOME"] = str(hf_home)
    os.environ["HUGGINGFACE_HUB_CACHE"] = str(hf_home / "hub")
    os.environ["TRANSFORMERS_CACHE"] = str(hf_home / "transformers")
    os.environ["TORCH_HOME"] = str(CACHE / "torch")
    os.environ["XDG_CACHE_HOME"] = str(CACHE)
    os.environ["HF_HUB_DISABLE_TELEMETRY"] = "1"
    os.environ["HF_HUB_DISABLE_XET"] = "1"
    os.environ["GRADIO_TEMP_DIR"] = str(TMP / "gradio")
    os.environ["GRADIO_ANALYTICS_ENABLED"] = "False"
    os.environ["TMPDIR"] = str(TMP)
    os.environ["PYTHONNOUSERSITE"] = "1"

    if offline is None:
        offline = os.environ.get("HINDI_VOICE_OFFLINE", "0") == "1"
    os.environ["HF_HUB_OFFLINE"] = "1" if offline else "0"
    os.environ["TRANSFORMERS_OFFLINE"] = "1" if offline else "0"
    _apply_hf_offline_constant(offline)
    _configure_logging()


def _apply_hf_offline_constant(offline: bool) -> None:
    """huggingface_hub copies HF_HUB_OFFLINE into a constant at import time."""
    try:
        import huggingface_hub.constants as hf_constants
    except Exception:
        return
    if hasattr(hf_constants, "HF_HUB_OFFLINE"):
        hf_constants.HF_HUB_OFFLINE = offline
    if hasattr(hf_constants, "HF_HUB_DISABLE_XET"):
        hf_constants.HF_HUB_DISABLE_XET = True


def _configure_logging() -> None:
    LOGS.mkdir(parents=True, exist_ok=True)
    logger = logging.getLogger("hindi_voice_lab")
    if logger.handlers:
        return
    logger.setLevel(logging.INFO)
    handler = logging.FileHandler(LOGS / "app.log", encoding="utf-8")
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
    logger.addHandler(handler)


def port() -> int:
    raw = os.environ.get("HINDI_VOICE_PORT", str(DEFAULT_PORT))
    try:
        value = int(raw)
    except ValueError as exc:
        raise RuntimeError(f"HINDI_VOICE_PORT must be an integer, got {raw!r}.") from exc
    if not 1 <= value <= 65535:
        raise RuntimeError(f"HINDI_VOICE_PORT {value} is outside 1-65535.")
    return value


def requested_device() -> str:
    value = os.environ.get("HINDI_VOICE_DEVICE", "auto").strip().lower()
    if value not in {"auto", "cpu", "mps", "cuda"}:
        raise RuntimeError("HINDI_VOICE_DEVICE must be auto, cpu, mps, or cuda.")
    return value


def offline_enabled() -> bool:
    return os.environ.get("HINDI_VOICE_OFFLINE", "0") == "1"


def confine(path: Path, root: Path | None = None) -> Path:
    """Resolve a path and reject anything outside the lab (or a given root)."""
    base = (root or ROOT).resolve()
    resolved = Path(path).expanduser().resolve()
    if not resolved.is_relative_to(base):
        raise ValueError(f"Path is outside the allowed directory: {path}")
    return resolved
