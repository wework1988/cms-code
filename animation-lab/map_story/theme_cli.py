"""CMS and worker entry point for map appearance templates."""
from __future__ import annotations

import argparse
import json
import sys

from map_story.themes import apply_token_overrides, export_builtin_json, public_theme, theme_for, theme_ids


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Resolve map appearance templates")
    parser.add_argument("command", choices=("list", "snapshot", "export"))
    args = parser.parse_args(argv)
    try:
        if args.command == "export":
            path = export_builtin_json()
            json.dump({"ok": True, "path": str(path)}, sys.stdout)
            return 0
        if args.command == "list":
            json.dump({
                "ok": True,
                "default_theme_id": "documentary_relief_bold",
                "themes": [public_theme(theme_for(theme_id)) for theme_id in sorted(theme_ids())],
            }, sys.stdout, ensure_ascii=False)
            return 0
        body = json.loads(sys.stdin.read() or "{}")
        style = str(body.get("style") or body.get("base_id") or "documentary_relief_bold")
        base_theme = body.get("base_theme") if isinstance(body.get("base_theme"), dict) else None
        theme = apply_token_overrides(
            style,
            body.get("overrides") or None,
            theme_id=body.get("theme_id"),
            name=body.get("name"),
            base_theme=base_theme,
        )
        json.dump({"ok": True, "theme": theme}, sys.stdout, ensure_ascii=False)
        return 0
    except (ValueError, KeyError, json.JSONDecodeError) as error:
        json.dump({"ok": False, "error": str(error)}, sys.stdout, ensure_ascii=False)
        return 1


if __name__ == "__main__":
    sys.exit(main())
