#!/usr/bin/env python3
"""Resolve API keys: Drupal bundle → worker .env → automation repo .env (read-only)."""

from __future__ import annotations

import os
import json
import time
import fcntl
from dataclasses import dataclass
from pathlib import Path
from contextlib import contextmanager

from dotenv import load_dotenv


def load_all_env(automation_repo: Path | None = None) -> None:
    """Load worker .env then automation repo .env (does not override existing vars)."""
    load_dotenv()
    if automation_repo is None:
        raw = os.environ.get("AUTOMATION_REPO", "")
        automation_repo = Path(raw).expanduser() if raw else None
    if automation_repo and automation_repo.is_dir():
        automation_env = automation_repo / ".env"
        if automation_env.is_file():
            load_dotenv(automation_env, override=False)


def resolve_keys(bundle: dict | None = None) -> dict[str, str]:
    """
    Merge API keys from Drupal bundle with environment fallbacks.

    Priority (first non-empty wins):
      1. Drupal config (admin form → bundle api_keys)
      2. Worker .env / automation repo .env fallbacks
    """
    bundle = bundle or {}
    from_drupal = bundle.get("api_keys") or {}
    names = ("deepseek_api_key", "anthropic_api_key", "elevenlabs_api_key")
    out: dict[str, str] = {}
    env_fallbacks = {
        "deepseek_api_key": ("DEEPSEEK_API_KEY",),
        "anthropic_api_key": ("ANTHROPIC_API_KEY", "anthropic_api_key"),
        # automation repo .env uses eleven_labs_api_key; generate_audio.py accepts all of these
        "elevenlabs_api_key": ("ELEVENLABS_API_KEY", "eleven_labs_api_key", "ELEVEN_LABS_API_KEY"),
    }
    for name in names:
        val = (from_drupal.get(name) or "").strip()
        if not val:
            for env_name in env_fallbacks[name]:
                val = (os.environ.get(env_name) or "").strip()
                if val:
                    break
        out[name] = val
    return out


def _split_key_list(raw: str) -> list[str]:
    return [k.strip() for k in raw.split(",") if k.strip()]


def _deepseek_pool_candidates(primary_key: str = "") -> list[str]:
    keys: list[str] = []
    if primary_key.strip():
        keys.append(primary_key.strip())
    keys.extend(_split_key_list(os.environ.get("DEEPSEEK_API_KEYS", "")))
    env_single = (os.environ.get("DEEPSEEK_API_KEY") or "").strip()
    if env_single:
        keys.append(env_single)

    unique: list[str] = []
    seen: set[str] = set()
    for k in keys:
        if k not in seen:
            seen.add(k)
            unique.append(k)
    return unique


def _mask_key(key: str) -> str:
    if len(key) <= 8:
        return "***"
    return f"{key[:4]}…{key[-4:]}"


def _pid_alive(pid: int) -> bool:
    if pid <= 0:
        return False
    try:
        os.kill(pid, 0)
        return True
    except OSError:
        return False


def _pool_dir() -> Path:
    p = Path(__file__).resolve().parent / ".runtime"
    p.mkdir(parents=True, exist_ok=True)
    return p


def _pool_state_path() -> Path:
    return _pool_dir() / "deepseek-key-pool.json"


def _pool_lock_path() -> Path:
    return _pool_dir() / "deepseek-key-pool.lock"


def _read_pool_state(path: Path) -> dict[str, list[int]]:
    if not path.is_file():
        return {}
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    if not isinstance(raw, dict):
        return {}
    out: dict[str, list[int]] = {}
    for key, pids in raw.items():
        if not isinstance(key, str) or not isinstance(pids, list):
            continue
        cleaned = [int(pid) for pid in pids if isinstance(pid, int) and _pid_alive(pid)]
        if cleaned:
            out[key] = cleaned
    return out


def _write_pool_state(path: Path, state: dict[str, list[int]]) -> None:
    path.write_text(json.dumps(state, ensure_ascii=True, sort_keys=True), encoding="utf-8")


@dataclass
class DeepSeekKeyLease:
    key: str
    from_pool: bool = False

    def release(self) -> None:
        if not self.from_pool:
            return
        lock_path = _pool_lock_path()
        state_path = _pool_state_path()
        lock_path.touch(exist_ok=True)
        with lock_path.open("r+", encoding="utf-8") as lockf:
            fcntl.flock(lockf.fileno(), fcntl.LOCK_EX)
            state = _read_pool_state(state_path)
            entries = [pid for pid in state.get(self.key, []) if pid != os.getpid() and _pid_alive(pid)]
            if entries:
                state[self.key] = entries
            else:
                state.pop(self.key, None)
            _write_pool_state(state_path, state)
            fcntl.flock(lockf.fileno(), fcntl.LOCK_UN)


def acquire_deepseek_key(keys: dict[str, str]) -> DeepSeekKeyLease:
    primary = (keys.get("deepseek_api_key") or "").strip()
    candidates = _deepseek_pool_candidates(primary)
    if not candidates:
        raise SystemExit(
            "error: no DeepSeek API key found.\n"
            "  Option A — Drupal: /admin/config/content/story-pipeline → DeepSeek key\n"
            "  Option B — worker or automation repo .env: DEEPSEEK_API_KEY=...\n"
            "  Option C — worker .env key pool: DEEPSEEK_API_KEYS=key1,key2"
        )

    if len(candidates) == 1:
        return DeepSeekKeyLease(candidates[0], from_pool=False)

    lock_path = _pool_lock_path()
    state_path = _pool_state_path()
    lock_path.touch(exist_ok=True)
    with lock_path.open("r+", encoding="utf-8") as lockf:
        fcntl.flock(lockf.fileno(), fcntl.LOCK_EX)
        state = _read_pool_state(state_path)

        best_key = candidates[0]
        best_count = 10**9
        for key in candidates:
            count = len(state.get(key, []))
            if count < best_count:
                best_count = count
                best_key = key
            if count == 0:
                break

        state.setdefault(best_key, []).append(os.getpid())
        _write_pool_state(state_path, state)
        fcntl.flock(lockf.fileno(), fcntl.LOCK_UN)

    print(f"[keys] allocated DeepSeek key from pool: {_mask_key(best_key)}")
    return DeepSeekKeyLease(best_key, from_pool=True)


@contextmanager
def leased_deepseek_key(keys: dict[str, str]):
    lease = acquire_deepseek_key(keys)
    try:
        yield lease.key
    finally:
        lease.release()


def require_deepseek(keys: dict[str, str]) -> str:
    key = keys.get("deepseek_api_key", "")
    if not key:
        raise SystemExit(
            "error: no DeepSeek API key found.\n"
            "  Option A — Drupal: /admin/config/content/story-pipeline → DeepSeek key\n"
            "  Option B — worker or automation repo .env: DEEPSEEK_API_KEY=..."
        )
    return key


def require_elevenlabs(keys: dict[str, str]) -> str:
    key = keys.get("elevenlabs_api_key", "")
    if not key:
        raise SystemExit(
            "error: no ElevenLabs API key found.\n"
            "  Option A — Drupal: /admin/config/content/story-pipeline → ElevenLabs key\n"
            "  Option B — worker or automation repo .env: eleven_labs_api_key=..."
        )
    return key


def apply_asset_root_from_bundle(bundle: dict | None) -> None:
    """Use Drupal story_asset_path when STORY_ASSET_ROOT is not in worker .env."""
    if (os.environ.get("STORY_ASSET_ROOT") or "").strip():
        return
    path = ((bundle or {}).get("story_asset_path") or "").strip()
    if path:
        os.environ["STORY_ASSET_ROOT"] = path
