#!/usr/bin/env bash
# Story Pipeline Worker — launcher
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT"

export PATH="/Applications/MAMP/Library/bin/mysql80/bin:${PATH:-}"

if [[ -f .env ]]; then
  set -a
  # shellcheck source=/dev/null
  source .env
  set +a
elif [[ ! -f .env ]]; then
  echo "Copy .env.example to .env and set DRUPAL_API_KEY"
  exit 1
fi

if [[ ! -d .venv ]]; then
  python3 -m venv .venv
fi

# Ensure pipeline deps (openai, etc.) — idempotent
.venv/bin/pip install -q -r requirements.txt

PY="${ROOT}/.venv/bin/python"
export PYTHONUNBUFFERED=1

cmd="${1:-help}"
shift || true

case "$cmd" in
  install-deps)
    .venv/bin/pip install -r requirements.txt
    echo "Dependencies installed in .venv"
    ;;
  storyboard)
    exec "$PY" -u run_storyboard.py "$@"
    ;;
  scene-breakdown)
    exec "$PY" -u run_scene_breakdown.py "$@"
    ;;
  generate)
    exec "$PY" -u run_generate_story.py "$@"
    ;;
  elevenlabs)
    exec "$PY" -u run_elevenlabs.py "$@"
    ;;
  translate-english|translate_english)
    exec "$PY" -u run_translate_english.py "$@"
    ;;
  full)
    exec "$PY" -u run_full_pipeline.py "$@"
    ;;
  multi)
    exec bash "${ROOT}/run_multi.sh" "$@"
    ;;
  worker)
    exec "$PY" -u worker.py "$@"
    ;;
  info)
    curl -s "${DRUPAL_BASE_URL}/api/story-pipeline/stories/${1:-1}" \
      -H "X-Story-Pipeline-Key: ${DRUPAL_API_KEY}" | python3 -m json.tool
    ;;
  *)
    cat <<EOF
Usage:
  ./run.sh install-deps             Install/update Python dependencies
  ./run.sh storyboard 1              Run storyboard for Drupal node 1
  ./run.sh storyboard 1 --max-step 3 Stop after Stage B
  ./run.sh scene-breakdown 98        Generate scenes from updated-scene-breakdown.md
  ./run.sh scene-breakdown 98 --force           Re-run DeepSeek scene breakdown
  ./run.sh scene-breakdown 98 --export-only --breakdown /path/to/breakdown.md
  ./run.sh storyboard 86 --resume       Continue from saved Stage A+B → Stage C (skip redo)
  ./run.sh storyboard 94 --resume --fill-prompt-gaps  Generate missing Stage C scenes only
  ./run.sh storyboard 1 --elevenlabs Also generate eleven-labs/ MP3s after storyboard
  ./run.sh elevenlabs 1              ElevenLabs only (no storyboard re-run)
  ./run.sh translate-english 96      Hindi scene.txt → English scenes + full story
  ./run.sh translate-english 96 --force  Overwrite existing English outputs
  ./run.sh full 1                    Full pipeline (YouTube→script→storyboard→audio)
  ./run.sh generate 1                Generate script from YouTube URLs
  ./run.sh multi full 2 4 5          Run same job on multiple stories (background)
  ./run.sh worker --story-id 1         Auto-detect pipeline
  ./run.sh info 1                    Show story JSON from Drupal

Setup:
  cp .env.example .env
  # Edit DRUPAL_API_KEY (drush story-pipeline:info in myresearch2)
  # Set DeepSeek keys in Drupal: /admin/config/content/story-pipeline
EOF
    ;;
esac
