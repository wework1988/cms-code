#!/usr/bin/env bash
# Create hindi-voice-lab/.venv and install the pinned Python packages.
# Does not modify the parent project, shell startup files, or system Python.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

PYTHON_RELEASE="20261009"
PYTHON_VERSION="3.11.17"
STANDALONE="${ROOT}/.python/bin/python3.11"

download_standalone() {
  local arch asset url
  arch="$(uname -m)"
  case "$arch" in
    arm64|aarch64) asset="cpython-${PYTHON_VERSION}+${PYTHON_RELEASE}-aarch64-apple-darwin-install_only.tar.gz" ;;
    x86_64) asset="cpython-${PYTHON_VERSION}+${PYTHON_RELEASE}-x86_64-apple-darwin-install_only.tar.gz" ;;
    *)
      echo "No pinned standalone CPython build is configured for ${arch}." >&2
      echo "Install Python ${PYTHON_VERSION} yourself and re-run this script so python3.11 is on PATH." >&2
      exit 1
      ;;
  esac
  url="https://github.com/astral-sh/python-build-standalone/releases/download/${PYTHON_RELEASE}/${asset}"
  mkdir -p "${ROOT}/tmp" "${ROOT}/.python-src"
  echo "Downloading CPython ${PYTHON_VERSION} (${PYTHON_RELEASE}) into hindi-voice-lab/.python"
  curl -fL --retry 3 -o "${ROOT}/tmp/${asset}" "$url"
  rm -rf "${ROOT}/.python" "${ROOT}/.python-src/python"
  tar -xzf "${ROOT}/tmp/${asset}" -C "${ROOT}/.python-src"
  mv "${ROOT}/.python-src/python" "${ROOT}/.python"
  rm -f "${ROOT}/tmp/${asset}"
}

if [[ -x "$STANDALONE" ]]; then
  PY="$STANDALONE"
elif command -v python3.11 >/dev/null 2>&1; then
  PY="$(command -v python3.11)"
else
  download_standalone
  PY="$STANDALONE"
fi

version="$("$PY" -c 'import sys; print(".".join(map(str, sys.version_info[:3])))')"
case "$version" in
  3.11.*) ;;
  *)
    echo "Need Python 3.11.x. ${PY} is ${version}." >&2
    exit 1
    ;;
esac

if [[ ! -x "${ROOT}/.venv/bin/python" ]]; then
  "$PY" -m venv "${ROOT}/.venv"
fi

export PIP_CACHE_DIR="${ROOT}/cache/pip"
export TMPDIR="${ROOT}/tmp"
export PYTHONNOUSERSITE=1
mkdir -p "$PIP_CACHE_DIR" "$TMPDIR"
"${ROOT}/.venv/bin/python" -m pip install --upgrade pip
"${ROOT}/.venv/bin/python" -m pip install -r "${ROOT}/requirements.txt"
echo "Setup finished. Next: scripts/download_models.py, then scripts/run.sh"
