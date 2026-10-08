#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
export PYTHONPATH="${ROOT}/.python-libs:${ROOT}${PYTHONPATH:+:$PYTHONPATH}"
exec python3 "${ROOT}/helper/server.py" --config "${ROOT}/config.json" "$@"
