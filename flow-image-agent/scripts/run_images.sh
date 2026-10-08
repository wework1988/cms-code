#!/usr/bin/env bash
# One-command Flow image generation into a CMS story folder.
# Example:
#   ./scripts/run_images.sh 164-how-captain-saved-video-done --first-two
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

if [[ ! -d node_modules/playwright ]]; then
  if [[ -d ../playright-automation/node_modules/playwright ]]; then
    export NODE_PATH="${ROOT}/../playright-automation/node_modules${NODE_PATH:+:$NODE_PATH}"
  else
    echo "Installing playwright…"
    npm install --no-fund --no-audit
  fi
fi

exec node "$ROOT/run-images.mjs" "$@"
