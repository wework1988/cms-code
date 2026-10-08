"""Loopback auth, origin checks, and filesystem sandboxing."""

from __future__ import annotations

import os
import secrets
from pathlib import Path, PurePosixPath


class SecurityError(Exception):
    pass


def generate_pairing_token() -> str:
    return secrets.token_urlsafe(32)


def load_or_create_token(token_path: Path) -> str:
    token_path.parent.mkdir(parents=True, exist_ok=True)
    if token_path.is_file():
        token = token_path.read_text(encoding="utf-8").strip()
        if token:
            return token
    token = generate_pairing_token()
    flags = os.O_WRONLY | os.O_CREAT | os.O_TRUNC
    fd = os.open(str(token_path), flags, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as fh:
        fh.write(token + "\n")
    try:
        os.chmod(token_path, 0o600)
    except OSError:
        pass
    return token


def origin_allowed(origin: str | None, patterns: list[str]) -> bool:
    if not origin:
        # Same-origin fetch from extension may omit Origin on some browsers;
        # callers must still present the pairing token.
        return True
    for pattern in patterns:
        if pattern.endswith("://*"):
            prefix = pattern[:-1]  # chrome-extension://
            if origin.startswith(prefix):
                return True
        elif origin == pattern:
            return True
    return False


def resolve_under_roots(path: Path | str, roots: list[Path]) -> Path:
    """
    Resolve path and require it to stay within one configured root.
    Rejects path traversal and symlink escapes outside roots.
    """
    candidate = Path(path).expanduser()
    # Resolve without following final symlink for existence checks later;
    # resolve(strict=False) still resolves parents.
    resolved = candidate.resolve(strict=False)

    for root in roots:
        root_resolved = root.resolve(strict=False)
        try:
            resolved.relative_to(root_resolved)
        except ValueError:
            continue
        # Walk parents; if any symlink jumps outside root, reject.
        check = resolved
        while True:
            if check.is_symlink():
                target = check.resolve(strict=False)
                try:
                    target.relative_to(root_resolved)
                except ValueError as exc:
                    raise SecurityError(
                        f"Symlink escape blocked: {check} → {target}"
                    ) from exc
            if check == root_resolved or check.parent == check:
                break
            check = check.parent
        return resolved

    raise SecurityError(f"Path outside configured story roots: {resolved}")


def safe_relpath_key(story_dir: Path, roots: list[Path]) -> str:
    resolved = resolve_under_roots(story_dir, roots)
    for root in roots:
        root_resolved = root.resolve(strict=False)
        try:
            rel = resolved.relative_to(root_resolved)
            # Prefer category/name when root is a category folder's parent
            return str(PurePosixPath(*rel.parts))
        except ValueError:
            continue
    return resolved.name


def extract_bearer(authorization: str | None, header_token: str | None) -> str | None:
    if header_token:
        return header_token.strip()
    if not authorization:
        return None
    parts = authorization.split(None, 1)
    if len(parts) == 2 and parts[0].lower() == "bearer":
        return parts[1].strip()
    return None
