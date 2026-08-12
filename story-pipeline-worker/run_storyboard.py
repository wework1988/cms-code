#!/usr/bin/env python3
"""
Run storyboard pipeline (Stage A→B→C) for a Drupal story node.

Fetches bundle from Drupal → temp workspace → deepseek_pipeline.py → uploads results.
Does NOT modify the automation repo (read-only subprocess).
"""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
import tempfile
import threading
from pathlib import Path

from drupal_client import DrupalStoryClient
from secrets import apply_asset_root_from_bundle, leased_deepseek_key, load_all_env, resolve_keys
from asset_store import finalize_drupal_payload, seed_workspace_from_assets, sync_storyboard_outputs
from audio_languages import generate_story_audio, sync_generated_audio
from workspace import prepare_storyboard_workspace


def _safe_int(value: object, default: int) -> int:
    try:
        return int(str(value).strip())
    except (TypeError, ValueError):
        return default


def _upsert_cli_arg(cmd: list[str], flag: str, value: str) -> list[str]:
    """Set/replace a CLI arg pair like `--batch 4`."""
    out = list(cmd)
    if flag in out:
        i = out.index(flag)
        if i + 1 < len(out):
            out[i + 1] = value
            return out
        out.append(value)
        return out
    out.extend([flag, value])
    return out


def _repo_has_pipeline(repo: Path) -> bool:
    return (repo / "crime-section" / "helper" / "deepseek_pipeline.py").is_file()


def automation_repo(bundle: dict | None = None) -> Path:
    candidates: list[Path] = []
    for raw in (
        ((bundle or {}).get("automation_repo_path") or "").strip(),
        (os.environ.get("AUTOMATION_REPO") or "").strip(),
    ):
        if raw:
            candidates.append(Path(raw).expanduser())
    mirror = (os.environ.get("STORY_ASSET_MIRROR") or "").strip()
    if mirror:
        candidates.append(Path(mirror).expanduser().parent)
    candidates.append(Path("/Users/averma/project/research-story-17thmay-automation"))

    seen: set[str] = set()
    for p in candidates:
        key = str(p)
        if key in seen:
            continue
        seen.add(key)
        if not p.is_dir():
            continue
        resolved = p.resolve()
        if _repo_has_pipeline(resolved):
            os.environ["AUTOMATION_REPO"] = str(resolved)
            return resolved

    tried = ", ".join(str(p) for p in candidates if str(p))
    sys.exit(
        "error: deepseek_pipeline.py not found. Set AUTOMATION_REPO to the "
        f"research-story automation repo (tried: {tried})"
    )


def pipeline_script() -> Path:
    script = automation_repo() / "crime-section" / "helper" / "deepseek_pipeline.py"
    if not script.is_file():
        sys.exit(f"error: deepseek_pipeline.py not found at {script}")
    return script


def export_script() -> Path:
    script = automation_repo() / "crime-section" / "helper" / "export_prompt_derivatives.py"
    if not script.is_file():
        sys.exit(f"error: export_prompt_derivatives.py not found at {script}")
    return script


def ensure_image_prompts_only(story_dir: Path) -> Path | None:
    """Return path to image-prompts-only.txt, deriving from prompt.txt if needed."""
    target = story_dir / "image-prompts-only.txt"
    if target.is_file():
        return target

    prompt = story_dir / "prompt.txt"
    if not prompt.is_file():
        return None

    subprocess.run(
        [
            sys.executable,
            str(export_script()),
            "--prompt",
            str(prompt),
        ],
        check=True,
        cwd=str(automation_repo() / "crime-section" / "helper"),
    )
    return target if target.is_file() else None


def collect_outputs(workspace: Path, slug: str) -> dict:
    story_dir = workspace / "stories" / slug
    config = story_dir / f"output_config_{slug}.md"
    breakdown = story_dir / f"output_story_breakdown_{slug}.md"
    prompt = story_dir / "prompt.txt"
    scene = story_dir / "scene.txt"
    image_prompts = ensure_image_prompts_only(story_dir)

    out: dict = {"status": "storyboard_done"}
    if config.is_file():
        out["stage_a_output"] = config.read_text(encoding="utf-8")
    if breakdown.is_file():
        out["stage_b_output"] = breakdown.read_text(encoding="utf-8")
    if prompt.is_file():
        out["prompt_file_content"] = prompt.read_text(encoding="utf-8")
    if scene.is_file():
        out["scene_file_content"] = scene.read_text(encoding="utf-8")
    if image_prompts and image_prompts.is_file():
        out["image_prompts_file_content"] = image_prompts.read_text(encoding="utf-8")
    return out


def run_elevenlabs_step(
    repo: Path,
    story_dir: Path,
    bundle: dict,
    keys: dict[str, str],
    payload: dict,
) -> None:
    generate_story_audio(repo, story_dir, bundle, keys, payload)


def _start_incremental_sync(
    story_dir: Path,
    slug: str,
    story_id: int | str,
    title: str,
    story_type: str,
    interval: int = 10,
) -> threading.Event:
    """Background thread: syncs workspace outputs to STORY_ASSET_ROOT every `interval` seconds."""
    stop = threading.Event()

    def _loop() -> None:
        while not stop.wait(interval):
            try:
                sync_storyboard_outputs(story_dir, slug, story_id, title, story_type)
            except Exception as exc:  # noqa: BLE001
                print(f"[assets] incremental sync warning: {exc}")

    t = threading.Thread(target=_loop, daemon=True, name=f"cms-sync-{slug}")
    t.start()
    return stop


def run_storyboard(
    story_id: int,
    max_step: int = 4,
    keep_workspace: bool = False,
    elevenlabs: bool = False,
    resume: bool = False,
    fill_prompt_gaps: bool = False,
) -> None:
    client = DrupalStoryClient()

    print(f"[drupal] GET story {story_id}")
    story = client.get_story(story_id)
    print(f"  title: {story.get('title')}")
    print(f"  type:  {story.get('story_type')}")
    print(f"  status: {story.get('status')}")

    print(f"[drupal] GET bundle (storyboard)")
    bundle = client.get_bundle(story_id, pipeline="storyboard")
    apply_asset_root_from_bundle(bundle)

    repo = automation_repo(bundle)
    load_all_env(repo)

    keys = resolve_keys(bundle)
    if not (bundle.get("api_keys") or {}).get("deepseek_api_key"):
        print("[keys] using DEEPSEEK_API_KEY/DEEPSEEK_API_KEYS from .env (Drupal Crime key not set)")
    workspace_parent = Path(__file__).resolve().parent / ".workspace"
    workspace_parent.mkdir(exist_ok=True)
    tmp = Path(tempfile.mkdtemp(prefix=f"story-{story_id}-", dir=workspace_parent))

    try:
        root, slug = prepare_storyboard_workspace(bundle, tmp)
        print(f"[workspace] {root}")
        print(f"[workspace] slug={slug}")

        story_dir = root / "stories" / slug
        _title = story.get("title") or ""
        _story_type = story.get("story_type") or "general"

        if resume:
            restored = seed_workspace_from_assets(
                story_dir, slug, story_id, _title, _story_type
            )
            if not restored:
                sys.exit(
                    "error: --resume found no saved Stage A/B files in STORY_ASSET_ROOT. "
                    "Run a full storyboard first, or check story_asset_path in Drupal settings."
                )
            required = {f"output_config_{slug}.md", f"output_story_breakdown_{slug}.md"}
            if not required.issubset(set(restored)):
                sys.exit(
                    f"error: --resume needs Stage A + B files ({', '.join(sorted(required))}). "
                    f"Found: {', '.join(restored) or 'none'}"
                )
            print("[resume] Stage A + B will be skipped; pipeline continues from Stage C")

        client.update_story(story_id, {"status": "storyboard_running"})

        env = os.environ.copy()
        env["DEEPSEEK_CONFIG_PATH"] = str(root / "deepseek.config.example.ini")

        # Guardrail: Storyboard Stage B often truncates around 65k output tokens.
        # Enforce a safer floor unless caller explicitly set a higher/lower value.
        configured_b = _safe_int((bundle.get("settings") or {}).get("max_tokens_b"), 131072)
        current_b = _safe_int(env.get("DEEPSEEK_MAX_TOKENS_B"), configured_b)
        effective_b = max(131072, current_b, configured_b)
        env["DEEPSEEK_MAX_TOKENS_B"] = str(effective_b)
        if effective_b > current_b:
            print(f"[pipeline] raised DEEPSEEK_MAX_TOKENS_B to {effective_b} for Stage B stability")

        # Stage C stability: enforce a high token ceiling by default so UI-triggered
        # runs don't fail due to incomplete scene-window outputs.
        configured_c = _safe_int((bundle.get("settings") or {}).get("max_tokens_c"), 98304)
        current_c = _safe_int(env.get("DEEPSEEK_MAX_TOKENS_C"), configured_c)
        effective_c = max(98304, current_c, configured_c)
        env["DEEPSEEK_MAX_TOKENS_C"] = str(effective_c)
        if effective_c > current_c:
            print(f"[pipeline] raised DEEPSEEK_MAX_TOKENS_C to {effective_c} for Stage C stability")

        # Give Stage C more chances before hard-failing.
        current_c_retries = _safe_int(env.get("STAGE_C_BATCH_RETRIES"), 6)
        effective_c_retries = max(6, current_c_retries)
        env["STAGE_C_BATCH_RETRIES"] = str(effective_c_retries)
        if effective_c_retries > current_c_retries:
            print(f"[pipeline] raised STAGE_C_BATCH_RETRIES to {effective_c_retries}")

        # Prefer content tokens over reasoning tokens unless user already set this.
        if not (env.get("DEEPSEEK_THINKING") or "").strip():
            env["DEEPSEEK_THINKING"] = "0"
            print("[pipeline] DEEPSEEK_THINKING=0 (default for storyboard stability)")

        # Stability default: run Stage B/C sequentially unless explicitly overridden.
        if not (env.get("STAGE_B_PARALLEL_CALLS") or "").strip():
            env["STAGE_B_PARALLEL_CALLS"] = "1"
            print("[pipeline] STAGE_B_PARALLEL_CALLS=1 (sequential default)")
        if not (env.get("STAGE_C_PARALLEL_BATCHES") or "").strip():
            env["STAGE_C_PARALLEL_BATCHES"] = "1"
            print("[pipeline] STAGE_C_PARALLEL_BATCHES=1 (sequential default)")
        if not (env.get("STAGE_C_DISABLE_SINGLE_SCENE_FALLBACK") or "").strip():
            env["STAGE_C_DISABLE_SINGLE_SCENE_FALLBACK"] = "1"
            print("[pipeline] STAGE_C_DISABLE_SINGLE_SCENE_FALLBACK=1 (batch-first mode)")

        if resume:
            env["DEEPSEEK_THINKING"] = "0"
            print("[resume] DEEPSEEK_THINKING=0 (more output budget for Stage C)")

        if fill_prompt_gaps:
            if not resume:
                restored = seed_workspace_from_assets(
                    story_dir, slug, story_id, _title, _story_type
                )
                if not restored:
                    sys.exit(
                        "error: --fill-prompt-gaps needs saved prompt.txt + breakdown in STORY_ASSET_ROOT"
                    )
            env["DEEPSEEK_THINKING"] = "0"
            print("[fill-prompt-gaps] generating only missing Stage C scenes")

        cmd = [
            sys.executable,
            str(pipeline_script()),
            "--crime-root",
            str(root),
            "--story",
            slug,
            "--max-step",
            str(max_step),
            "--story-source",
            str(root / "story-to-run" / "story.txt"),
        ]
        if fill_prompt_gaps:
            cmd.append("--fill-prompt-gaps")
        model = (bundle.get("settings") or {}).get("model")
        if model:
            cmd.extend(["--model", model])

        batch = (bundle.get("settings") or {}).get("scene_batch")
        if batch:
            cmd.extend(["--batch", str(batch)])

        print(f"[pipeline] {' '.join(cmd)}")

        sync_stop = _start_incremental_sync(story_dir, slug, story_id, _title, _story_type)
        print(f"[assets] incremental sync started → cms-generate-stories/{_story_type}/{slug}/")

        try:
            with leased_deepseek_key(keys) as deepseek_key:
                env["DEEPSEEK_API_KEY"] = deepseek_key
                try:
                    subprocess.run(cmd, env=env, check=True)
                except subprocess.CalledProcessError:
                    # Auto-recovery for common Stage C missing-scene failures:
                    # keep batch mode and retry with smaller batches.
                    if max_step < 4 or fill_prompt_gaps:
                        raise
                    print(
                        "[recovery] Stage C failed. Retrying in batch mode with smaller scene batches."
                    )
                    recovery_base_cmd = list(cmd)

                    current_batch = 8
                    if "--batch" in recovery_base_cmd:
                        bi = recovery_base_cmd.index("--batch")
                        if bi + 1 < len(recovery_base_cmd):
                            current_batch = _safe_int(recovery_base_cmd[bi + 1], 8)

                    # Multi-pass batch-only recovery strategy.
                    plans: list[tuple[str, dict[str, str]]] = [
                        (
                            str(max(2, min(current_batch, 6))),
                            {},
                        ),
                        (
                            "4",
                            {
                                "STAGE_C_BATCH_RETRIES": "6",
                                "DEEPSEEK_MAX_TOKENS_C": "98304",
                            },
                        ),
                        (
                            "2",
                            {
                                "STAGE_C_BATCH_RETRIES": "7",
                                "DEEPSEEK_MAX_TOKENS_C": "98304",
                            },
                        ),
                    ]

                    last_err: subprocess.CalledProcessError | None = None
                    for idx, (batch_value, extra_env) in enumerate(plans, start=1):
                        recovery_env = env.copy()
                        recovery_env["STAGE_C_PARALLEL_BATCHES"] = "1"
                        recovery_env["STAGE_B_PARALLEL_CALLS"] = "1"
                        recovery_env["STAGE_C_DISABLE_SINGLE_SCENE_FALLBACK"] = "1"
                        for k, v in extra_env.items():
                            recovery_env[k] = v

                        recovery_cmd = _upsert_cli_arg(
                            list(recovery_base_cmd),
                            "--batch",
                            batch_value,
                        )
                        print(
                            f"[recovery] pass {idx}/{len(plans)} "
                            f"(batch={batch_value})"
                        )
                        print(f"[recovery] {' '.join(recovery_cmd)}")
                        try:
                            subprocess.run(recovery_cmd, env=recovery_env, check=True)
                            last_err = None
                            break
                        except subprocess.CalledProcessError as rec_err:
                            last_err = rec_err
                            print(
                                f"[recovery] pass {idx} failed "
                                f"(exit={rec_err.returncode})."
                            )

                    if last_err is not None:
                        raise last_err
        finally:
            sync_stop.set()
            print("[assets] incremental sync stopped")

        payload = collect_outputs(root, slug)
        if "prompt_file_content" not in payload:
            sys.exit("error: prompt.txt was not created — check pipeline logs")

        assets_on_disk = sync_storyboard_outputs(
            story_dir, slug, story_id, _title, _story_type
        ) is not None

        if elevenlabs and max_step >= 4:
            run_elevenlabs_step(repo, story_dir, bundle, keys, payload)
            if sync_generated_audio(story_dir, slug, story_id, _title, _story_type, payload):
                assets_on_disk = True

        payload = finalize_drupal_payload(payload, assets_on_disk=assets_on_disk)

        print(f"[drupal] POST update story {story_id}")
        result = client.update_story(story_id, payload)
        print(f"  status: {result.get('status')}")
        print(f"  prompt_file_url: {result.get('prompt_file_url')}")
        print(f"  image_prompts_file_url: {result.get('image_prompts_file_url')}")
        print(f"  eleven_labs_file_urls: {len(result.get('eleven_labs_file_urls') or [])} file(s)")
        print("done.")

    except subprocess.CalledProcessError as exc:
        client.update_story(story_id, {"status": "failed", "story_meta": f"Pipeline exit {exc.returncode}"})
        raise
    except Exception as exc:
        client.update_story(story_id, {"status": "failed", "story_meta": str(exc)})
        raise
    finally:
        if keep_workspace:
            print(f"[workspace] kept at {tmp}")
        else:
            shutil.rmtree(tmp, ignore_errors=True)


def main() -> None:
    parser = argparse.ArgumentParser(description="Run storyboard for a Drupal story node")
    parser.add_argument("story_id", type=int, help="Drupal node ID (e.g. 1)")
    parser.add_argument("--max-step", type=int, default=4, choices=[1, 2, 3, 4])
    parser.add_argument("--elevenlabs", action="store_true", help="Generate eleven-labs/ MP3s after step 4")
    parser.add_argument("--keep-workspace", action="store_true")
    parser.add_argument(
        "--resume",
        action="store_true",
        help="Restore saved Stage A/B from STORY_ASSET_ROOT and continue from Stage C",
    )
    parser.add_argument(
        "--fill-prompt-gaps",
        action="store_true",
        help="Stage C only: generate missing image prompts vs Stage B breakdown (needs existing prompt.txt)",
    )
    args = parser.parse_args()
    run_storyboard(
        args.story_id,
        max_step=args.max_step,
        keep_workspace=args.keep_workspace,
        elevenlabs=args.elevenlabs,
        resume=args.resume,
        fill_prompt_gaps=args.fill_prompt_gaps,
    )


if __name__ == "__main__":
    main()
