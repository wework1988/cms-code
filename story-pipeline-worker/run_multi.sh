#!/usr/bin/env bash
# Run the same pipeline job on multiple Drupal story node IDs.
#
# Default: SEQUENTIAL — story 2 finishes, then story 4 starts, etc.
#
# Examples:
#   ./run_multi.sh full 2 4 5
#   ./run_multi.sh --parallel full 2 4 5    # all at once (old behaviour)
#   ./run_multi.sh storyboard-elevenlabs 2 4
#
# Outputs upload to Drupal when each story completes; files go to STORY_ASSET_ROOT.

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT"

MODE="sequential"
if [[ "${1:-}" == "--parallel" ]]; then
  MODE="parallel"
  shift
elif [[ "${1:-}" == "--sequential" ]]; then
  MODE="sequential"
  shift
fi

if [[ $# -lt 2 ]]; then
  cat <<EOF
Usage: ./run_multi.sh [OPTIONS] JOB STORY_ID [STORY_ID ...]

Options:
  --sequential   Run one story after another (default)
  --parallel     Run all stories at the same time

Jobs:
  full                  YouTube → script → storyboard → audio (if needed)
  storyboard            Stages A–C only
  storyboard-elevenlabs Storyboard + ElevenLabs MP3s
  generate              YouTube → script only
  elevenlabs            Audio only (script must exist)

Examples:
  ./run_multi.sh full 2 4 5
  ./run_multi.sh --parallel full 2 4

Tips:
  - Sequential queue runs for many hours total; safe to close Terminal after start.
  - Keep Mac awake: caffeinate -dims
  - Queue log: logs/queue-JOB-*.log
  - Per-story detail still in each story's run output inside the queue log.
EOF
  exit 1
fi

JOB="$1"
shift
IDS=("$@")

mkdir -p logs

run_cmd() {
  local id="$1"
  case "$JOB" in
    full)
      ./run.sh full "$id"
      ;;
    storyboard)
      ./run.sh storyboard "$id"
      ;;
    storyboard-elevenlabs)
      ./run.sh storyboard "$id" --elevenlabs
      ;;
    generate)
      ./run.sh generate "$id"
      ;;
    elevenlabs)
      ./run.sh elevenlabs "$id"
      ;;
    *)
      echo "error: unknown job '$JOB'" >&2
      exit 1
      ;;
  esac
}

for id in "${IDS[@]}"; do
  if ! [[ "$id" =~ ^[0-9]+$ ]]; then
    echo "error: invalid story id '$id' (use Drupal node numbers)" >&2
    exit 1
  fi
done

if [[ "$MODE" == "parallel" ]]; then
  for id in "${IDS[@]}"; do
    ts="$(date +%Y%m%d-%H%M%S)"
    log="${ROOT}/logs/story-${id}-${JOB}-${ts}.log"
    case "$JOB" in
      full) nohup ./run.sh full "$id" >>"$log" 2>&1 & ;;
      storyboard) nohup ./run.sh storyboard "$id" >>"$log" 2>&1 & ;;
      storyboard-elevenlabs) nohup ./run.sh storyboard "$id" --elevenlabs >>"$log" 2>&1 & ;;
      generate) nohup ./run.sh generate "$id" >>"$log" 2>&1 & ;;
      elevenlabs) nohup ./run.sh elevenlabs "$id" >>"$log" 2>&1 & ;;
    esac
    echo "Started story #${id} (${JOB}) in parallel — PID $! — log: ${log}"
    sleep 2
  done
  echo ""
  echo "All jobs launched in parallel."
  exit 0
fi

# Sequential: one background process, stories run one after another.
QUEUE_LOG="${ROOT}/logs/queue-${JOB}-$(date +%Y%m%d-%H%M%S).log"
IDS_CSV="$(IFS=,; echo "${IDS[*]}")"

(
  set +e
  echo "Sequential queue: ${JOB} for stories: ${IDS_CSV}"
  echo "Started: $(date)"
  for id in "${IDS[@]}"; do
    echo ""
    echo "========== Story #${id} started $(date) =========="
    if run_cmd "$id"; then
      echo "========== Story #${id} finished OK $(date) =========="
    else
      code=$?
      echo "========== Story #${id} FAILED exit ${code} $(date) — continuing to next story =========="
    fi
  done
  echo ""
  echo "Sequential queue complete: $(date)"
) >>"$QUEUE_LOG" 2>&1 &

PID=$!
echo "Sequential queue started — ${#IDS[@]} story/stories, one after another"
echo "  PID: ${PID}"
echo "  stories: ${IDS[*]}"
echo "  log: ${QUEUE_LOG}"
echo ""
echo "Safe to close Terminal. Tail progress: tail -f ${QUEUE_LOG}"
