"""Locate the map renderer runtime without relying on a CMS process PATH."""
from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

LAB = Path(__file__).resolve().parent.parent
RENDER_JS = LAB / "map-story" / "render.mjs"
_KNOWN_NODE = (
    "/opt/homebrew/bin/node",
    "/usr/local/bin/node",
)


class RuntimeError_(RuntimeError):
    """Preflight failure. Named to avoid shadowing the builtin in callers."""


def resolve_node_executable(environ: dict | None = None) -> str:
    """Return an absolute Node executable. A bare 'node' on a short PATH is not enough."""
    env = os.environ if environ is None else environ
    candidates: list[str] = []
    explicit = (env.get("NODE") or "").strip()
    if explicit and explicit != "node":
        candidates.append(explicit)
    candidates.extend(_KNOWN_NODE)
    search = "/opt/homebrew/bin:/usr/local/bin:" + (env.get("PATH") or "/usr/bin:/bin")
    found = shutil.which("node", path=search)
    if found:
        candidates.append(found)
    seen = set()
    for candidate in candidates:
        if not candidate or candidate in seen or candidate == "node":
            continue
        seen.add(candidate)
        path = Path(candidate)
        if path.is_file() and os.access(path, os.X_OK):
            return str(path.resolve())
    raise RuntimeError(
        "Node.js is required to render map videos and was not found. "
        "Looked for an absolute executable at /opt/homebrew/bin/node, /usr/local/bin/node, "
        "and on PATH. Set NODE to the absolute path of the node binary."
    )


def preflight_map_runtime(environ: dict | None = None) -> dict:
    """Fail before a model request when the renderer cannot start."""
    if not RENDER_JS.is_file():
        raise RuntimeError(f"Map renderer is missing: {RENDER_JS}")
    node = resolve_node_executable(environ)
    env = os.environ.copy() if environ is None else dict(environ)
    env["PATH"] = str(Path(node).parent) + os.pathsep + (env.get("PATH") or "/usr/bin:/bin")
    env.pop("PLAYWRIGHT_CHROME_CDP", None)
    try:
        proc = subprocess.run(
            [node, "--version"],
            capture_output=True,
            text=True,
            env=env,
            timeout=15,
            check=False,
        )
    except OSError as error:
        raise RuntimeError(f"Node.js at {node} could not be started: {error}") from None
    if proc.returncode != 0 or not (proc.stdout or "").startswith("v"):
        detail = (proc.stderr or proc.stdout or "").strip()
        raise RuntimeError(f"Node.js at {node} did not report a version. {detail}")
    return {"node": node, "node_version": proc.stdout.strip(), "render_js": str(RENDER_JS)}
