#!/usr/bin/env python3
"""Loopback HTTP helper for Flow image agent (story discovery, jobs, image save)."""

from __future__ import annotations

import argparse
import json
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlparse

# Allow `python helper/server.py` from package root or helper/
HELPER_DIR = Path(__file__).resolve().parent
PACKAGE_ROOT = HELPER_DIR.parent
if str(PACKAGE_ROOT) not in sys.path:
    sys.path.insert(0, str(PACKAGE_ROOT))
LIBS = PACKAGE_ROOT / ".python-libs"
if LIBS.is_dir() and str(LIBS) not in sys.path:
    sys.path.insert(0, str(LIBS))

from helper.config import load_config  # noqa: E402
from helper.images import ImageValidationError, copy_validated_download  # noqa: E402
from helper.manifest import (  # noqa: E402
    create_or_resume_job,
    load_manifest,
    next_queued_scene,
    next_retryable_scene,
    save_manifest,
    summarize,
    update_scene,
)
from helper.prompts import (  # noqa: E402
    detect_format,
    filter_scene_range,
    parse_image_prompts_file,
    scene_filename_stem,
)
from helper.security import (  # noqa: E402
    SecurityError,
    extract_bearer,
    load_or_create_token,
    origin_allowed,
    resolve_under_roots,
)
from helper.stories import discover_stories, find_existing_image, resolve_story  # noqa: E402


class AppState:
    def __init__(self, config: dict[str, Any]):
        self.config = config
        self.token = load_or_create_token(Path(config["token_file"]))
        self.roots: list[Path] = list(config["story_roots_resolved"])
        self.lock = threading.RLock()
        # job_id -> images_dir for quick lookup
        self.jobs: dict[str, Path] = {}
        state_dir = Path(config["state_dir"])
        state_dir.mkdir(parents=True, exist_ok=True)
        self.index_path = state_dir / "jobs-index.json"
        self._load_index()

    def _load_index(self) -> None:
        if self.index_path.is_file():
            data = json.loads(self.index_path.read_text(encoding="utf-8"))
            self.jobs = {k: Path(v) for k, v in data.items()}

    def _save_index(self) -> None:
        payload = {k: str(v) for k, v in self.jobs.items()}
        self.index_path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")

    def register_job(self, job_id: str, images_dir: Path) -> None:
        self.jobs[job_id] = images_dir
        self._save_index()


def json_response(handler: BaseHTTPRequestHandler, status: int, body: dict[str, Any]) -> None:
    data = json.dumps(body).encode("utf-8")
    handler.send_response(status)
    handler.send_header("Content-Type", "application/json; charset=utf-8")
    handler.send_header("Content-Length", str(len(data)))
    handler.send_header("Cache-Control", "no-store")
    handler.end_headers()
    handler.wfile.write(data)


def read_json(handler: BaseHTTPRequestHandler) -> dict[str, Any]:
    length = int(handler.headers.get("Content-Length") or "0")
    if length <= 0:
        return {}
    if length > 20_000_000:
        raise ValueError("Request body too large")
    raw = handler.rfile.read(length)
    if not raw:
        return {}
    return json.loads(raw.decode("utf-8"))


class Handler(BaseHTTPRequestHandler):
    server_version = "FlowImageAgentHelper/1.0"
    app: AppState

    def log_message(self, fmt: str, *args: Any) -> None:
        # Avoid logging tokens or full prompt bodies.
        sys.stderr.write("%s - %s\n" % (self.address_string(), fmt % args))

    def _unauthorized(self, message: str = "Unauthorized") -> None:
        json_response(self, 401, {"ok": False, "error": message})

    def _forbidden(self, message: str) -> None:
        json_response(self, 403, {"ok": False, "error": message})

    def _bad(self, message: str, status: int = 400) -> None:
        json_response(self, status, {"ok": False, "error": message})

    def _auth(self) -> bool:
        if self.client_address[0] not in ("127.0.0.1", "::1"):
            self._forbidden("Only loopback clients are allowed")
            return False
        origin = self.headers.get("Origin")
        if not origin_allowed(origin, self.app.config.get("allowed_origins") or []):
            self._forbidden("Origin not allowed")
            return False
        token = extract_bearer(
            self.headers.get("Authorization"),
            self.headers.get("X-Flow-Agent-Token"),
        )
        if not token or token != self.app.token:
            self._unauthorized("Missing or invalid pairing token")
            return False
        return True

    def do_OPTIONS(self) -> None:  # noqa: N802
        origin = self.headers.get("Origin") or "*"
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", origin)
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header(
            "Access-Control-Allow-Headers",
            "Authorization, Content-Type, X-Flow-Agent-Token",
        )
        self.send_header("Access-Control-Max-Age", "600")
        self.end_headers()

    def _cors(self) -> None:
        origin = self.headers.get("Origin")
        if origin and origin_allowed(origin, self.app.config.get("allowed_origins") or []):
            self.send_header("Access-Control-Allow-Origin", origin)
            self.send_header("Vary", "Origin")

    def do_GET(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        path = parsed.path.rstrip("/") or "/"
        if path == "/health":
            # Health is local-only but does not require token (for quick process checks).
            if self.client_address[0] not in ("127.0.0.1", "::1"):
                self._forbidden("Only loopback clients are allowed")
                return
            json_response(
                self,
                200,
                {
                    "ok": True,
                    "service": "flow-image-agent-helper",
                    "version": "1.0.0",
                },
            )
            return

        if not self._auth():
            return

        qs = parse_qs(parsed.query)
        try:
            if path == "/stories":
                stories = discover_stories(self.app.roots)
                json_response(
                    self,
                    200,
                    {
                        "ok": True,
                        "stories": [
                            {
                                "key": s.key,
                                "path": str(s.path),
                                "category": s.category,
                                "story_id": s.story_id,
                                "title": s.title,
                                "prompt_count": s.prompt_count,
                                "completed_images": s.completed_images,
                                "images_dir": str(s.images_dir),
                                "prompt_file": str(s.prompt_file),
                            }
                            for s in stories
                        ],
                    },
                )
                return

            if path.startswith("/stories/") and path.endswith("/preview"):
                key = path[len("/stories/") : -len("/preview")]
                story = resolve_story(key, self.app.roots)
                prompts = parse_image_prompts_file(story.prompt_file)
                fmt = detect_format(story.prompt_file.read_text(encoding="utf-8"))
                scene_from = int(qs["from"][0]) if qs.get("from") else None
                scene_to = int(qs["to"][0]) if qs.get("to") else None
                if qs.get("first_two", [""])[0] in ("1", "true", "yes"):
                    nums = sorted(p.scene for p in prompts)[:2]
                    selected = filter_scene_range(prompts, scene_list=nums)
                else:
                    selected = filter_scene_range(prompts, scene_from, scene_to)
                completed = []
                expected = []
                for p in selected:
                    existing = find_existing_image(story.images_dir, p.scene)
                    stem = scene_filename_stem(p.scene)
                    expected.append(f"{stem}.<ext>")
                    if existing:
                        completed.append({"scene": p.scene, "path": str(existing)})
                manifest = load_manifest(story.images_dir, self.app.roots)
                json_response(
                    self,
                    200,
                    {
                        "ok": True,
                        "format": fmt,
                        "story": {
                            "key": story.key,
                            "title": story.title,
                            "category": story.category,
                            "story_id": story.story_id,
                            "path": str(story.path),
                        },
                        "prompt_file": str(story.prompt_file),
                        "images_dir": str(story.images_dir),
                        "detected_scenes": [p.scene for p in prompts],
                        "selected_scenes": [p.scene for p in selected],
                        "expected_filenames": expected,
                        "already_completed": completed,
                        "completed_count": len(completed),
                        "settings": {
                            "model": self.app.config["model"],
                            "aspect_ratio": self.app.config["aspect_ratio"],
                            "outputs_per_prompt": self.app.config["outputs_per_prompt"],
                            "download_variant": self.app.config["download_variant"],
                        },
                        "existing_job": manifest.to_dict() if manifest else None,
                        "prompts": [
                            {
                                "scene": p.scene,
                                "prompt_hash": p.prompt_hash,
                                "text": p.text,
                                "filename_stem": p.filename_stem,
                            }
                            for p in selected
                        ],
                    },
                )
                return

            if path.startswith("/jobs/"):
                job_id = path.split("/")[2]
                images_dir = self.app.jobs.get(job_id)
                if not images_dir:
                    self._bad("Unknown job id", 404)
                    return
                manifest = load_manifest(images_dir, self.app.roots)
                if not manifest or manifest.job_id != job_id:
                    self._bad("Job manifest missing", 404)
                    return
                json_response(
                    self,
                    200,
                    {"ok": True, "job": manifest.to_dict(), "summary": summarize(manifest)},
                )
                return

            self._bad("Not found", 404)
        except KeyError as exc:
            self._bad(str(exc), 404)
        except (ValueError, SecurityError) as exc:
            self._bad(str(exc))
        except Exception as exc:  # pragma: no cover
            self._bad(f"Server error: {exc}", 500)

    def do_POST(self) -> None:  # noqa: N802
        if not self._auth():
            return
        parsed = urlparse(self.path)
        path = parsed.path.rstrip("/") or "/"
        try:
            body = read_json(self)
        except Exception as exc:
            self._bad(f"Invalid JSON: {exc}")
            return

        try:
            with self.app.lock:
                if path == "/jobs":
                    self._start_job(body)
                    return
                parts = [p for p in path.split("/") if p]
                # /jobs/{id}/pause|resume|stop|retry-failed|claim-next
                if len(parts) == 3 and parts[0] == "jobs":
                    job_id, action = parts[1], parts[2]
                    self._job_action(job_id, action, body)
                    return
                # /jobs/{id}/scenes/{n}/status|/save
                if (
                    len(parts) == 5
                    and parts[0] == "jobs"
                    and parts[2] == "scenes"
                    and parts[4] in ("status", "save")
                ):
                    job_id, scene_s, action = parts[1], parts[3], parts[4]
                    scene = int(scene_s)
                    if action == "status":
                        self._scene_status(job_id, scene, body)
                    else:
                        self._scene_save(job_id, scene, body)
                    return
            self._bad("Not found", 404)
        except RuntimeError as exc:
            self._bad(str(exc), 409)
        except KeyError as exc:
            self._bad(str(exc), 404)
        except (ValueError, SecurityError, ImageValidationError) as exc:
            self._bad(str(exc))
        except Exception as exc:  # pragma: no cover
            self._bad(f"Server error: {exc}", 500)

    def _get_manifest(self, job_id: str):
        images_dir = self.app.jobs.get(job_id)
        if not images_dir:
            # Try discover via story path in body later; index miss
            raise KeyError(f"Unknown job id: {job_id}")
        manifest = load_manifest(images_dir, self.app.roots)
        if not manifest or manifest.job_id != job_id:
            raise KeyError(f"Job manifest missing: {job_id}")
        return manifest

    def _start_job(self, body: dict[str, Any]) -> None:
        story_key = body.get("story_key") or body.get("story")
        if not story_key:
            raise ValueError("story_key is required")
        story = resolve_story(str(story_key), self.app.roots)
        prompts = parse_image_prompts_file(story.prompt_file)
        if body.get("first_two"):
            nums = sorted(p.scene for p in prompts)[:2]
            selected = filter_scene_range(prompts, scene_list=nums)
        elif body.get("scene_list"):
            selected = filter_scene_range(prompts, scene_list=list(body["scene_list"]))
        else:
            selected = filter_scene_range(
                prompts,
                body.get("scene_from"),
                body.get("scene_to"),
            )
        settings = {
            "model": self.app.config["model"],
            "aspect_ratio": self.app.config["aspect_ratio"],
            "outputs_per_prompt": self.app.config["outputs_per_prompt"],
            "download_variant": self.app.config["download_variant"],
        }
        manifest = create_or_resume_job(
            story_key=story.key,
            story_path=story.path,
            images_dir=story.images_dir,
            prompt_file=story.prompt_file,
            selected=selected,
            roots=self.app.roots,
            regenerate=bool(body.get("regenerate")),
            settings=settings,
        )
        self.app.register_job(manifest.job_id, Path(manifest.images_dir))
        json_response(
            self,
            200,
            {
                "ok": True,
                "job": manifest.to_dict(),
                "summary": summarize(manifest),
                "prompts": [
                    {
                        "scene": p.scene,
                        "prompt_hash": p.prompt_hash,
                        "text": p.text,
                        "filename_stem": p.filename_stem,
                    }
                    for p in selected
                ],
            },
        )

    def _job_action(self, job_id: str, action: str, body: dict[str, Any]) -> None:
        manifest = self._get_manifest(job_id)
        if action == "pause":
            manifest.control = "paused"
            manifest.lock_owner = None
            save_manifest(manifest, self.app.roots)
            json_response(self, 200, {"ok": True, "job": manifest.to_dict()})
            return
        if action == "stop":
            manifest.control = "stopped"
            manifest.lock_owner = None
            save_manifest(manifest, self.app.roots)
            json_response(
                self,
                200,
                {
                    "ok": True,
                    "job": manifest.to_dict(),
                    "note": (
                        "Stop cannot cancel a generation already submitted to Google "
                        "unless Flow exposes a cancellation action."
                    ),
                },
            )
            return
        if action == "resume":
            manifest.control = "running"
            save_manifest(manifest, self.app.roots)
            json_response(self, 200, {"ok": True, "job": manifest.to_dict(), "summary": summarize(manifest)})
            return
        if action == "retry-failed":
            for key, scene in list(manifest.scenes.items()):
                if scene.get("status") == "failed" and scene.get("error_category") != "policy_rejection":
                    scene["status"] = "queued"
                    scene["error_message"] = None
                    manifest.scenes[key] = scene
            manifest.control = "running"
            save_manifest(manifest, self.app.roots)
            json_response(self, 200, {"ok": True, "job": manifest.to_dict(), "summary": summarize(manifest)})
            return
        if action == "claim-next":
            if manifest.control == "paused":
                json_response(self, 200, {"ok": True, "scene": None, "reason": "paused"})
                return
            if manifest.control == "stopped":
                json_response(self, 200, {"ok": True, "scene": None, "reason": "stopped"})
                return
            if manifest.active_scene is not None and body.get("force") is not True:
                active = manifest.scenes.get(str(manifest.active_scene))
                if active and active.get("status") not in ("completed", "failed", "needs_review", "queued"):
                    json_response(
                        self,
                        409,
                        {
                            "ok": False,
                            "error": (
                                f"Scene {manifest.active_scene} is still {active.get('status')}. "
                                "Resolve or mark needs_review before claiming another."
                            ),
                        },
                    )
                    return
            retry_mode = bool(body.get("retry_failed"))
            nxt = next_retryable_scene(manifest) if retry_mode else next_queued_scene(manifest)
            if nxt is None:
                json_response(self, 200, {"ok": True, "scene": None, "reason": "done", "summary": summarize(manifest)})
                return
            owner = body.get("owner") or "extension"
            if manifest.lock_owner and manifest.lock_owner != owner and manifest.active_scene:
                raise RuntimeError("Another worker holds the story lock")
            manifest.lock_owner = owner
            manifest.control = "running"
            update_scene(
                manifest,
                nxt.scene,
                self.app.roots,
                status="configuring",
                attempt_count=nxt.attempt_count + 1,
                flow_project_url=body.get("flow_project_url"),
            )
            # reload
            manifest = self._get_manifest(job_id)
            scene = manifest.scenes[str(nxt.scene)]
            # Attach prompt text from file
            story_prompts = parse_image_prompts_file(Path(manifest.prompt_file))
            text = next(p.text for p in story_prompts if p.scene == nxt.scene)
            json_response(
                self,
                200,
                {
                    "ok": True,
                    "scene": {
                        **scene,
                        "text": text,
                        "filename_stem": scene_filename_stem(nxt.scene),
                    },
                    "settings": manifest.settings,
                    "summary": summarize(manifest),
                },
            )
            return
        raise ValueError(f"Unknown job action: {action}")

    def _scene_status(self, job_id: str, scene: int, body: dict[str, Any]) -> None:
        manifest = self._get_manifest(job_id)
        allowed = {
            "status",
            "flow_result_id",
            "flow_project_url",
            "download_id",
            "download_path",
            "error_category",
            "error_message",
            "width",
            "height",
            "image_format",
            "saved_path",
        }
        fields = {k: body[k] for k in allowed if k in body}
        if "status" in fields and fields["status"] not in (
            "queued",
            "configuring",
            "submitting",
            "generating",
            "upscaling",
            "downloading",
            "saving",
            "completed",
            "failed",
            "needs_review",
            "paused",
            "stopped",
        ):
            raise ValueError(f"Invalid status: {fields['status']}")
        if fields.get("status") == "needs_review":
            manifest.control = "paused"
        update_scene(manifest, scene, self.app.roots, **fields)
        manifest = self._get_manifest(job_id)
        json_response(self, 200, {"ok": True, "scene": manifest.scenes[str(scene)], "summary": summarize(manifest), "control": manifest.control})

    def _scene_save(self, job_id: str, scene: int, body: dict[str, Any]) -> None:
        manifest = self._get_manifest(job_id)
        download_path = body.get("download_path")
        if not download_path:
            raise ValueError("download_path is required")
        source = Path(download_path).expanduser()
        # Downloads live outside story roots — allow absolute path but require file exists.
        if not source.is_file():
            raise ValueError(f"download_path not found: {source}")
        # Soft check: reject obvious path tricks in story destination only.
        images_dir = resolve_under_roots(Path(manifest.images_dir), self.app.roots)
        update_scene(manifest, scene, self.app.roots, status="saving", download_path=str(source))
        saved = copy_validated_download(
            source,
            images_dir,
            scene,
            self.app.roots,
            overwrite=bool(body.get("regenerate")),
            min_width=int(self.app.config.get("min_landscape_width") or 2048),
            aspect_tolerance=float(self.app.config.get("aspect_tolerance") or 0.08),
        )
        update_scene(
            manifest,
            scene,
            self.app.roots,
            status="completed",
            saved_path=str(saved.path),
            image_format=saved.format,
            width=saved.width,
            height=saved.height,
            download_id=body.get("download_id"),
            download_path=str(source),
            flow_result_id=body.get("flow_result_id"),
            error_category=None,
            error_message=None,
        )
        # Clear lock if this was active
        manifest = self._get_manifest(job_id)
        if manifest.active_scene == scene:
            manifest.active_scene = None
        if not any(
            s.get("status") in ("queued", "configuring", "submitting", "generating", "upscaling", "downloading", "saving")
            for s in manifest.scenes.values()
        ):
            manifest.control = "idle"
            manifest.lock_owner = None
        save_manifest(manifest, self.app.roots)
        # Optionally remove original only after success if requested
        if body.get("delete_download_after_save"):
            try:
                source.unlink()
            except OSError:
                pass
        json_response(
            self,
            200,
            {
                "ok": True,
                "saved": {
                    "path": str(saved.path),
                    "format": saved.format,
                    "width": saved.width,
                    "height": saved.height,
                    "size_bytes": saved.size_bytes,
                },
                "scene": manifest.scenes[str(scene)],
                "summary": summarize(manifest),
            },
        )


def run(host: str, port: int, config_path: Path | None = None) -> None:
    config = load_config(config_path)
    # Force loopback
    if host not in ("127.0.0.1", "localhost", "::1"):
        raise SystemExit("Refusing to bind non-loopback host. Use 127.0.0.1")
    app = AppState(config)
    Handler.app = app
    httpd = ThreadingHTTPServer((host, port), Handler)
    print(f"Flow image agent helper listening on http://{host}:{port}", flush=True)
    print(f"Story roots: {', '.join(str(r) for r in app.roots if r.exists())}", flush=True)
    print("Pairing token written to token file (not printed). Load it in the extension.", flush=True)
    print(f"Token file: {config['token_file']}", flush=True)
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down.", flush=True)
        httpd.server_close()


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Flow image agent local helper")
    parser.add_argument("--host", default=None)
    parser.add_argument("--port", type=int, default=None)
    parser.add_argument("--config", type=Path, default=None)
    args = parser.parse_args(argv)
    config = load_config(args.config)
    host = args.host or config["host"]
    port = args.port or int(config["port"])
    run(host, port, args.config)


if __name__ == "__main__":
    main()
