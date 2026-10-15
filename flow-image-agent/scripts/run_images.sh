#!/usr/bin/env bash
# One-command Flow image generation into a CMS story folder.
# Example:
#   ./scripts/run_images.sh 164-how-captain-saved-video-done --first-two
#   ./scripts/run_images.sh 169-test-full-flow-image-generation --all
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

# Drupal/PHP launches workers with a tiny PATH — ensure Homebrew node is visible.
export PATH="/opt/homebrew/bin:/usr/local/bin:${PATH:-/usr/bin:/bin}"

resolve_node() {
  if [[ -n "${NODE_BIN:-}" && -x "${NODE_BIN}" ]]; then
    echo "${NODE_BIN}"
    return
  fi
  if command -v node >/dev/null 2>&1; then
    command -v node
    return
  fi
  for candidate in \
    /opt/homebrew/bin/node \
    /usr/local/bin/node \
    "$HOME/.nvm/versions/node/$(ls "$HOME/.nvm/versions/node" 2>/dev/null | tail -1)/bin/node"
  do
    if [[ -n "$candidate" && -x "$candidate" ]]; then
      echo "$candidate"
      return
    fi
  done
  return 1
}

NODE_BIN="$(resolve_node)" || {
  echo "ERROR: node not found. Install Node.js or set NODE_BIN=/path/to/node" >&2
  exit 127
}

if [[ ! -d node_modules/playwright ]]; then
  if [[ -d ../playright-automation/node_modules/playwright ]]; then
    export NODE_PATH="${ROOT}/../playright-automation/node_modules${NODE_PATH:+:$NODE_PATH}"
  else
    NPM_BIN="$(command -v npm || true)"
    if [[ -z "$NPM_BIN" && -x /opt/homebrew/bin/npm ]]; then
      NPM_BIN=/opt/homebrew/bin/npm
    fi
    if [[ -z "$NPM_BIN" ]]; then
      echo "ERROR: npm not found (needed to install playwright)" >&2
      exit 127
    fi
    echo "Installing playwright…"
    "$NPM_BIN" install --no-fund --no-audit
  fi
fi

exec "$NODE_BIN" "$ROOT/run-images.mjs" "$@"
