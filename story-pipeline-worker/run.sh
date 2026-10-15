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

# Prefer the editable bullet prompt from the automation mirror when present.
if [[ -z "${STORY_BULLET_PROMPT_PATH:-}" ]]; then
  _default_bullet_prompt="${STORY_ASSET_MIRROR:-}/bullet promt"
  if [[ -f "${_default_bullet_prompt}" ]]; then
    export STORY_BULLET_PROMPT_PATH="${_default_bullet_prompt}"
  fi
fi
unset _default_bullet_prompt 2>/dev/null || true

if [[ ! -d .venv ]]; then
  python3 -m venv .venv
fi

# Ensure pipeline deps (openai, etc.) — idempotent
if [[ "${1:-}" != "watchdog" ]]; then
  .venv/bin/pip install -q -r requirements.txt
fi

PY="${ROOT}/.venv/bin/python"
export PYTHONUNBUFFERED=1

cmd="${1:-help}"
shift || true

# Normal CMS jobs are durable; advanced text-only commands retain their CLI behavior.
if [[ "${PIPELINE_MANAGED:-0}" != "1" ]]; then
  case "$cmd" in
    storyboard)
      if [[ $# -eq 1 ]]; then exec "$PY" -u pipeline_watchdog.py enqueue storyboard "$1" --wait; fi
      if [[ $# -eq 2 && "$2" == "--elevenlabs" ]]; then exec "$PY" -u pipeline_watchdog.py enqueue storyboard "$1" --audio --wait; fi
      ;;
    full)
      if [[ $# -eq 1 ]]; then exec "$PY" -u pipeline_watchdog.py enqueue full "$1" --wait; fi
      ;;
    elevenlabs)
      if [[ $# -eq 1 ]]; then exec "$PY" -u pipeline_watchdog.py enqueue elevenlabs "$1" --wait; fi
      ;;
  esac
fi

case "$cmd" in
  watchdog)
    exec "$PY" -u pipeline_watchdog.py "$@"
    ;;
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
  animations)
    exec "$PY" -u run_animations.py "$@"
    ;;
  info)
    curl -s "${DRUPAL_BASE_URL}/api/story-pipeline/stories/${1:-1}" \
      -H "X-Story-Pipeline-Key: ${DRUPAL_API_KEY}" | python3 -m json.tool
    ;;
  *)
    cat <<EOF
Usage:
  ./run.sh install-deps             Install/update Python dependencies
  ./run.sh storyboard 1              Storyboard + Flow images + Digen videos
                                     (FLOW_IMAGES=0 / DIGEN_VIDEOS=0 to skip)
  ./run.sh storyboard 1 --max-step 3 Stop after Stage B (no Flow / Digen)
  ./run.sh scene-breakdown 98        Generate scenes from updated-scene-breakdown.md
  ./run.sh scene-breakdown 98 --force           Re-run DeepSeek scene breakdown
  ./run.sh scene-breakdown 98 --export-only --breakdown /path/to/breakdown.md
  ./run.sh storyboard 86 --resume       Continue from saved Stage A+B → Stage C (skip redo)
  ./run.sh storyboard 94 --resume --fill-prompt-gaps  Generate missing Stage C scenes only
  ./run.sh storyboard 1 --elevenlabs Storyboard + Flow + Digen + eleven-labs MP3s
  ./run.sh elevenlabs 1              ElevenLabs only (no storyboard re-run)
  ./run.sh translate-english 96      Hindi scene.txt → English scenes + full story
  ./run.sh translate-english 96 --force  Overwrite existing English outputs
  ./run.sh full 1                    Full pipeline (YouTube→script→storyboard→Flow→Digen→audio)
  ./run.sh generate 1                Generate script from YouTube URLs
  ./run.sh multi full 2 4 5          Run same job on multiple stories (background)
  ./run.sh worker --story-id 1         Auto-detect pipeline
  ./run.sh animations --snapshot PATH   Map, timeline, or documentary job from an immutable snapshot
  ./run.sh info 1                    Show story JSON from Drupal

Setup:
  cp .env.example .env
  # Edit DRUPAL_API_KEY (drush story-pipeline:info in myresearch2)
  # Set DeepSeek keys in Drupal: /admin/config/content/story-pipeline
EOF
    ;;
esac
