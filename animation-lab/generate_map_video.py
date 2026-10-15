#!/usr/bin/env python3
"""Plain-language map instruction → DeepSeek plan → resolve → compile → MP4.

Stages:
  A. DeepSeek planner (semantic-plan.json)
  B. Geographic resolver (registry + cached boundaries)
  C. Plan compiler (camera, highlights, callout → resolved-plan.json)
  D. Isolated Playwright renderer (map-story/)
  E. FFmpeg verification + representative frames

Examples:
  python3 generate_map_video.py \\
    --input examples/gorakhpur-map.txt \\
    --env-file ../story-pipeline-worker/.env \\
    --engine maplibre \\
    --duration 18 \\
    --output-dir output/gorakhpur-map

  python3 generate_map_video.py --input examples/gorakhpur-map.txt --plan-only \\
    --use-golden   # offline / no API

  python3 generate_map_video.py --plan output/gorakhpur-map/semantic-plan.json \\
    --engine openlayers --output-dir output/gorakhpur-map
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import secrets
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

from map_story.compile import atomic_write_json, compile_resolved_plan  # noqa: E402
from map_story.geo import GeoResolveError, load_registry, resolve_plan_places  # noqa: E402
from map_story.planner import generate_semantic_plan, golden_gorakhpur_plan, load_key  # noqa: E402
from map_story.schema import DEFAULT_STYLE, PlanValidationError, SUPPORTED_STYLES, validate_semantic_plan  # noqa: E402
from map_story.selection import SelectionError  # noqa: E402
from map_story.sequence import apply_palette  # noqa: E402


def run_renderer(resolved_path: Path, engine: str, output_dir: Path) -> None:
    resolved_path = resolved_path.resolve()
    output_dir = output_dir.resolve()
    render_js = ROOT / "map-story" / "render.mjs"
    if not render_js.is_file():
        raise RuntimeError(f"Missing renderer: {render_js}")
    env = os.environ.copy()
    # Prefer project Playwright browsers; do not attach to user Chrome.
    env.pop("PLAYWRIGHT_CHROME_CDP", None)
    cmd = [
        process_node(),
        str(render_js),
        "--plan",
        str(resolved_path),
        "--engine",
        engine,
        "--output-dir",
        str(output_dir),
    ]
    print("Running:", " ".join(cmd), flush=True)
    proc = subprocess.run(cmd, cwd=str(ROOT / "map-story"), env=env)
    if proc.returncode != 0:
        raise RuntimeError(f"Renderer failed with exit {proc.returncode}")


def process_node() -> str:
    from map_story.runtime import resolve_node_executable
    return resolve_node_executable()


def run_scene_directory(args) -> None:
    """Same scene-breakdown job the CMS queues. Does not read or write video/."""
    story_dir = args.story_dir.expanduser().resolve()
    scene_path = (args.scene_file or (story_dir / "scenes" / "scene.txt")).expanduser().resolve()
    from map_story.scene_source import load_scene_file
    document = load_scene_file(scene_path)
    if args.resume and args.output_dir and (args.output_dir / "snapshot.json").is_file():
        snapshot_path = args.output_dir / "snapshot.json"
    else:
        planner = _story_planner(args)
        prompt_body, prompt_meta = _load_master_prompt(args, planner)
        job_id = secrets.token_hex(8)
        job_dir = args.output_dir or (ROOT / "output" / "story-map-jobs" / story_dir.name / job_id)
        job_dir.mkdir(parents=True, exist_ok=True)
        prompt_hash = hashlib.sha256(prompt_body.encode("utf-8")).hexdigest()
        text = scene_path.read_text(encoding="utf-8-sig")
        snapshot = {
            "job_id": job_id,
            "input_mode": "scene_breakdown",
            "nid": None,
            "script": text,
            "script_source": "scenes/scene.txt",
            "script_hash": document.source_hash,
            "scene_text": text,
            "scene_source": {
                "path": str(scene_path),
                "text": text,
                "sha256": document.source_hash,
                "parser_version": document.parser_version,
                "scene_count": document.scene_count,
            },
            "story_root": str(story_dir),
            "master_prompt": prompt_body,
            "prompt_source": prompt_meta["prompt_source"],
            "prompt_id": prompt_meta.get("prompt_id"),
            "prompt_hash": prompt_hash,
            "prompt_revision": prompt_meta.get("prompt_id"),
            "language": args.language,
            "renderer": args.engine,
            "style": args.style,
            "duration_seconds": args.duration or 14,
            "max_clips": args.max_scenes,
            "max_selected_scenes": args.max_scenes,
            "scene_batch_scenes": 12,
            "scene_batch_chars": 12000,
            "animation_type": "map",
            "contract_version": "1.0",
            "renderer_settings": {
                "engine": args.engine,
                "width": args.width,
                "height": args.height,
                "fps": args.fps,
                "style": args.style,
            },
            "planner": planner,
            "model": args.model,
            "timeout": args.timeout,
            "env_file": str(args.env_file),
            "render": not args.plan_only,
            "created_unix": int(__import__("time").time()),
            "identity_fallback": True,
            "identity_fallback_max_calls": 24,
            "presentation_version": "2026.03-country-opening-v1",
            "opening_policy_default": "country_centered",
        }
        snapshot_path = job_dir / "snapshot.json"
        atomic_write_json(snapshot_path, snapshot)
        print(f"Scene file: {scene_path} ({document.scene_count} scenes, {document.source_hash[:12]})", flush=True)
        print(f"Job snapshot: {snapshot_path}", flush=True)
    sys.path.insert(0, str(ROOT.parent / "story-pipeline-worker"))
    from run_map_animations import run_job
    code = run_job(snapshot_path)
    if code:
        raise RuntimeError(f"Scene map job failed. See {snapshot_path.parent / 'progress.json'}")


def run_story(args) -> None:
    """Build the same snapshot a CMS map job writes, then run that worker."""
    script = args.story.read_text(encoding="utf-8")
    if not script.strip():
        raise ValueError("Story text is empty")
    planner = _story_planner(args)
    prompt_body, prompt_meta = _load_master_prompt(args, planner)
    job_id = secrets.token_hex(8)
    job_dir = _story_job_dir(args, job_id)
    job_dir.mkdir(parents=True, exist_ok=True)
    script_hash = hashlib.sha256(script.encode("utf-8")).hexdigest()
    prompt_hash = hashlib.sha256(prompt_body.encode("utf-8")).hexdigest() if prompt_body else None
    snapshot = {
        "job_id": job_id,
        "script": script,
        "script_source": "story_file",
        "script_path": str(args.story.resolve()),
        "script_hash": script_hash,
        "scene_text": args.scene_file.read_text(encoding="utf-8") if args.scene_file else "",
        "master_prompt": prompt_body,
        "prompt_source": prompt_meta["prompt_source"],
        "prompt_id": prompt_meta.get("prompt_id"),
        "prompt_path": prompt_meta.get("prompt_path"),
        "prompt_hash": prompt_hash,
        "language": args.language,
        "renderer": args.engine,
        "style": args.style,
        "duration_seconds": args.duration or 18,
        "max_clips": args.max_clips,
        "animation_type": "map",
        "contract_version": "1.0",
        "prompt_revision": prompt_meta.get("prompt_id"),
        "planning_settings": {
            "max_clips": args.max_clips,
            "duration_seconds": args.duration or 18,
            "language": args.language,
            "selection_provider": "local" if planner == "local" else "deepseek",
            "focus_planning_provider": "local" if planner == "local" else "deepseek",
        },
        "renderer_settings": {
            "engine": args.engine,
            "width": args.width,
            "height": args.height,
            "fps": args.fps,
            "style": args.style,
        },
        "planner": planner,
        "model": args.model,
        "timeout": args.timeout,
        "env_file": str(args.env_file),
        "render": not args.plan_only,
        "selection_provider": "local" if planner == "local" else "deepseek",
        "focus_planning_provider": "local" if planner == "local" else "deepseek",
        "presentation_version": "2026.03-country-opening-v1",
        "opening_policy_default": "country_centered",
        "created": None,
    }
    if args.selection:
        snapshot["selection"] = json.loads(args.selection.read_text(encoding="utf-8"))
        snapshot["selection_provider"] = "saved_selection"
    snapshot_path = job_dir / "snapshot.json"
    atomic_write_json(snapshot_path, snapshot)
    (job_dir / "progress.json").write_text(
        json.dumps({
            "status": "queued",
            "message": "Queued",
            "job_id": job_id,
            "script_source": "story_file",
            "script_hash": script_hash,
            "prompt_source": prompt_meta["prompt_source"],
            "prompt_id": prompt_meta.get("prompt_id"),
            "prompt_hash": prompt_hash,
            "clips": [],
        }, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(f"Job snapshot: {snapshot_path}", flush=True)
    sys.path.insert(0, str(ROOT.parent / "story-pipeline-worker"))
    from run_map_animations import run_job
    code = run_job(snapshot_path)
    if code:
        raise RuntimeError(f"Map job failed. See {job_dir / 'job-record.json'}")


def _story_planner(args) -> str:
    if args.planner == "local":
        return "local"
    if args.planner == "deepseek" or _has_key(args.env_file):
        return "deepseek"
    raise ValueError(
        "No DeepSeek key. Pass --planner local for an offline plan, or set DEEPSEEK_API_KEY. "
        "A generic local plan was not substituted."
    )


def _story_job_dir(args, job_id: str) -> Path:
    if args.output_dir is not None:
        return args.output_dir
    folder = args.story.parent.name
    if folder in {"script", "prompts", "audio"}:
        folder = args.story.parent.parent.name
    return ROOT / "output" / "story-map-jobs" / folder / job_id


def _load_master_prompt(args, planner: str) -> tuple[str, dict]:
    del planner  # Standalone story jobs always snapshot a concrete prompt revision.
    if args.master_prompt_file:
        path = args.master_prompt_file.expanduser().resolve()
        if not path.is_file():
            raise ValueError(f"Master prompt file was not found: {path}")
        body = path.read_bytes().decode("utf-8")
        if not body.strip():
            raise ValueError(f"Master prompt file is empty: {path}")
        return body, {"prompt_source": "master_prompt_file", "prompt_path": str(path), "prompt_id": None}
    row = _load_cms_map_prompt()
    return row["body"], {
        "prompt_source": "cms_prompt_revision",
        "prompt_path": None,
        "prompt_id": row["id"],
    }


def _load_cms_map_prompt() -> dict:
    """Read the newest saved map prompt revision. Do not invent a replacement."""
    settings = (ROOT.parent / "web" / "sites" / "default" / "settings.php").read_text(encoding="utf-8")
    marker = "$databases['default']['default'] = ["
    start = settings.rfind(marker)
    if start < 0:
        raise RuntimeError("Drupal database settings were not found. Pass --master-prompt-file.")
    block = settings[start:start + 800]

    def field(name: str) -> str:
        match = re.search(rf"'{name}'\s*=>\s*'([^']*)'", block)
        if not match:
            raise RuntimeError(f"Drupal database settings have no {name}. Pass --master-prompt-file.")
        return match.group(1)

    mysql = Path("/Applications/MAMP/Library/bin/mysql80/bin/mysql")
    if not mysql.is_file():
        mysql = Path("mysql")
    env = os.environ.copy()
    env["MYSQL_PWD"] = field("password")
    query = (
        "SELECT JSON_OBJECT('id', id, 'body', body) FROM story_pipeline_anim_prompt "
        "WHERE animation_type='map' ORDER BY id DESC LIMIT 1"
    )
    proc = subprocess.run(
        [
            str(mysql), "-h", field("host"), "-P", field("port"),
            "-u", field("username"), field("database"), "-N", "-e", query,
        ],
        capture_output=True,
        text=True,
        env=env,
    )
    if proc.returncode != 0 or not proc.stdout.strip():
        detail = (proc.stderr or "").strip().splitlines()[-1] if proc.stderr else "no saved map prompt"
        raise RuntimeError(
            f"Could not read the saved CMS map prompt ({detail}). Pass --master-prompt-file."
        )
    row = json.loads(proc.stdout)
    body = row.get("body") or ""
    if not str(body).strip() or not row.get("id"):
        raise RuntimeError("The saved CMS map prompt revision is empty. Pass --master-prompt-file.")
    return {"id": int(row["id"]), "body": body}


def _has_key(env_file: Path) -> bool:
    if os.environ.get("DEEPSEEK_API_KEY", "").strip():
        return True
    return env_file.is_file() and "DEEPSEEK_API_KEY" in env_file.read_text(encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--input", type=Path, help="Plain-language instruction file")
    parser.add_argument("--plan", type=Path, help="Existing semantic-plan.json (skip DeepSeek)")
    parser.add_argument("--plan-only", action="store_true", help="Plan + resolve + compile; do not render")
    parser.add_argument("--use-golden", action="store_true",
                        help="Use the built-in Gorakhpur semantic plan (no API call)")
    parser.add_argument("--env-file", type=Path, default=ROOT.parent / "story-pipeline-worker" / ".env")
    parser.add_argument("--model", default=os.environ.get("DEEPSEEK_MODEL", "deepseek-flash"))
    parser.add_argument("--engine", choices=("maplibre", "openlayers"), default="maplibre")
    parser.add_argument("--duration", type=float, default=None,
                        help="Target duration for a new plan. Ignored when replaying --plan unless --override-duration is set.")
    parser.add_argument("--override-duration", action="store_true",
                        help="When replaying --plan, require the saved duration to match --duration.")
    parser.add_argument("--fps", type=int, default=30)
    parser.add_argument("--width", type=int, default=1920)
    parser.add_argument("--height", type=int, default=1080)
    parser.add_argument("--language", default="hi")
    parser.add_argument("--style", default=DEFAULT_STYLE)
    parser.add_argument("--story", type=Path, help="Full story text. Selects map passages, then plans each clip.")
    parser.add_argument("--story-dir", type=Path, help="Story workspace. With --input-mode scene_breakdown, reads scenes/scene.txt.")
    parser.add_argument("--input-mode", choices=("full_story", "scene_breakdown"), default="full_story")
    parser.add_argument("--selection", type=Path, help="Saved selection.json. Skips passage selection and any model call.")
    parser.add_argument("--scene-file", type=Path, help="Optional scene.txt. In scene_breakdown mode this is the source file.")
    parser.add_argument("--max-clips", type=int, default=3)
    parser.add_argument("--max-scenes", type=int, default=10, help="First N suitable scenes when --input-mode scene_breakdown.")
    parser.add_argument("--resume", action="store_true", help="Continue an existing --output-dir scene job.")
    parser.add_argument("--planner", choices=("auto", "local", "deepseek"), default="auto")
    parser.add_argument("--master-prompt-file", type=Path,
                        help="Use this prompt text exactly. Do not replace it with the CMS prompt or a generic prompt.")
    parser.add_argument("--output-dir", type=Path, default=None,
                        help="Job directory. For --story, the default is output/story-map-jobs/<story>/<job-id>.")
    parser.add_argument("--timeout", type=int, default=180)
    parser.add_argument("--max-tokens", type=int, default=4000)
    args = parser.parse_args()

    try:
        if args.style not in SUPPORTED_STYLES:
            raise ValueError(f"Unsupported style '{args.style}'")
        if args.input_mode == "scene_breakdown" or args.story_dir:
            if args.input_mode != "scene_breakdown":
                raise ValueError("Pass --input-mode scene_breakdown with --story-dir.")
            run_scene_directory(args)
            return
        if args.story:
            run_story(args)
            return
        out = args.output_dir or (ROOT / "output" / "gorakhpur-map")
        out.mkdir(parents=True, exist_ok=True)
        semantic_path = out / "semantic-plan.json"
        resolved_path = out / "resolved-plan.json"

        if args.plan:
            semantic = json.loads(args.plan.read_text(encoding="utf-8"))
            # Replay uses the duration stored in the plan. --duration only applies
            # when --override-duration is set, and then it must match the file.
            expected = args.duration if args.override_duration else None
            if args.override_duration and expected is None:
                raise ValueError("--override-duration requires --duration")
            validate_semantic_plan(semantic, duration_seconds=expected)
            print(f"Loaded semantic plan: {args.plan} ({semantic.get('duration_seconds')}s)", flush=True)
        elif args.use_golden:
            semantic = golden_gorakhpur_plan(args.duration or 18)
            print("Using local golden Gorakhpur semantic plan (no API).", flush=True)
        else:
            if not args.input:
                raise ValueError("Provide --input, --plan, or --use-golden")
            instruction = args.input.read_text(encoding="utf-8")
            if not instruction.strip():
                raise ValueError("Input instruction is empty")
            print("Planning with DeepSeek…", flush=True)
            api_key = load_key(args.env_file)
            semantic = generate_semantic_plan(
                instruction,
                api_key,
                model=args.model,
                duration_seconds=args.duration or 18,
                language=args.language,
                style=args.style,
                timeout=args.timeout,
                max_tokens=args.max_tokens,
            )
            semantic["style"] = args.style
            if args.style == DEFAULT_STYLE:
                apply_palette(semantic)
            validate_semantic_plan(semantic, duration_seconds=args.duration or 18)

        atomic_write_json(semantic_path, semantic)
        print(f"Wrote {semantic_path}", flush=True)

        print("Resolving geography…", flush=True)
        registry = load_registry()
        places = resolve_plan_places(semantic, registry)
        print(f"  Resolved: {', '.join(places)}", flush=True)

        print("Compiling camera + styles…", flush=True)
        resolved = compile_resolved_plan(
            semantic,
            places,
            width=args.width,
            height=args.height,
            fps=args.fps,
            engine_hint=args.engine,
        )
        # Attach place geometry references only (paths), not raw polygons in huge form —
        # features already point at geojson URLs.
        resolved["semantic_plan_path"] = str(semantic_path.relative_to(ROOT)) if semantic_path.is_relative_to(ROOT) else str(semantic_path)
        resolved["registry_coverage"] = sorted(registry["places"].keys())
        atomic_write_json(resolved_path, resolved)
        print(f"Wrote {resolved_path}", flush=True)

        # Lightweight manifest seed
        manifest = {
            "schema_version": "1.0",
            "input": str(args.input) if args.input else None,
            "semantic_plan": str(semantic_path),
            "resolved_plan": str(resolved_path),
            "duration": resolved["duration"],
            "fps": resolved["fps"],
            "frames_expected": int(round(resolved["duration"] * resolved["fps"])),
            "engine_requested": args.engine,
            "style": semantic.get("style"),
            "places": list(places.keys()),
            "coverage": registry.get("coverage_note"),
        }
        atomic_write_json(out / "manifest.json", manifest)

        if args.plan_only:
            print("Plan-only complete (no render).", flush=True)
            return

        run_renderer(resolved_path, args.engine, out)
        print(f"Done. Outputs in {out.resolve()}", flush=True)
        print(f"  Video: {out / (args.engine + '.mp4')}", flush=True)
        print(f"  Contact sheet: {out / 'contact-sheet.png'}", flush=True)

    except (PlanValidationError, SelectionError, GeoResolveError, ValueError, RuntimeError, OSError) as error:
        print(f"Error: {error}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
