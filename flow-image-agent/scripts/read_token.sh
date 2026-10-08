#!/usr/bin/env bash
# Print pairing token for pasting into the extension (stdout only; not logged by helper).
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
TOKEN_FILE="${ROOT}/.local/pairing-token"
if [[ ! -f "$TOKEN_FILE" ]]; then
  echo "Token file missing. Start the helper once: ./scripts/run_helper.sh" >&2
  exit 1
fi
tr -d '\n' < "$TOKEN_FILE"
echo
