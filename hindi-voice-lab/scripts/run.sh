#!/usr/bin/env bash
# Launch the standalone Hindi Voice Lab. Does not start or stop the CMS.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

if [[ ! -x "${ROOT}/.venv/bin/python" ]]; then
  echo "Missing hindi-voice-lab/.venv. Run scripts/setup.sh first." >&2
  exit 1
fi

export PYTHONNOUSERSITE=1
export PYTHONUNBUFFERED=1
export TMPDIR="${ROOT}/tmp"
mkdir -p "$TMPDIR"
exec "${ROOT}/.venv/bin/python" "${ROOT}/app.py"
