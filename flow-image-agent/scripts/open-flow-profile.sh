#!/usr/bin/env bash
# Sign one Flow Gmail into its Chrome profile. Only one Chrome profile is open
# at a time: this script waits until you finish before it will open the next.
#
#   ./scripts/open-flow-profile.sh 2     # Gmail 2 only
#   ./scripts/open-flow-profile.sh all    # Gmail 2, then 3, then 4 (waits between each)
set -euo pipefail

ROOT="$(cd "$(dirname "$0")" && pwd)"

profile_dir() {
  local num="$1"
  if [[ "$num" == "1" ]]; then
    echo "$HOME/Library/Application Support/Google/Chrome-FlowAgent"
  else
    echo "$HOME/Library/Application Support/Google/Chrome-FlowAgent-${num}"
  fi
}

wait_until_done() {
  local num="$1"
  echo
  echo "Leave this Chrome window open. Sign into Gmail ${num}, then open Flow."
  echo "When that login is done, close Chrome and press Enter here."
  echo "Do not run another profile until this one is finished."
  if [[ -t 0 ]]; then
    read -r -p "Press Enter after Chrome is closed… " _
  else
    echo "Waiting until Google Chrome quits…"
    while pgrep -xq "Google Chrome" 2>/dev/null; do
      sleep 2
    done
  fi
  if pgrep -xq "Google Chrome" 2>/dev/null; then
    echo "Quitting Chrome before the next profile…"
    osascript -e 'tell application "Google Chrome" to quit' >/dev/null 2>&1 || true
    for _ in $(seq 1 20); do
      pgrep -xq "Google Chrome" 2>/dev/null || break
      sleep 0.5
    done
  fi
  echo "Profile ${num} done."
}

open_one() {
  local num="$1"
  local profile
  profile="$(profile_dir "$num")"
  echo
  echo "========================================"
  echo "Opening ONLY profile ${num}"
  echo "  $profile"
  echo "Other Flow profiles stay closed."
  echo "========================================"
  CHROME_FLOW_USER_DATA_DIR="$profile" \
  CHROME_FLOW_SKIP_SYNC=1 \
  CHROME_FLOW_FORCE_RESTART=1 \
  CHROME_FLOW_START_URL="https://labs.google/flow" \
    "$ROOT/start_chrome_debug.sh"
  wait_until_done "$num"
}

NUM="${1:-}"
if [[ "$NUM" == "all" ]]; then
  echo "Signing in Gmail 2, then 3, then 4 — one Chrome window at a time."
  open_one 2
  open_one 3
  open_one 4
  echo
  echo "All extra profiles were opened once. Enable account-2/3/4 in config.json."
  exit 0
fi

if [[ ! "$NUM" =~ ^[1-4]$ ]]; then
  echo "Usage:" >&2
  echo "  $0 2          # sign in Gmail 2 only, then wait" >&2
  echo "  $0 3          # sign in Gmail 3 only, then wait" >&2
  echo "  $0 4          # sign in Gmail 4 only, then wait" >&2
  echo "  $0 all        # Gmail 2, then 3, then 4 (one at a time)" >&2
  exit 1
fi

open_one "$NUM"
