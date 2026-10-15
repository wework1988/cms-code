#!/usr/bin/env bash
# Start Chrome with remote debugging using a NON-DEFAULT profile that is
# cloned from your normal Chrome login (Google requires this for DevTools).
#
# Default Chrome path cannot enable --remote-debugging-port:
#   "DevTools remote debugging requires a non-default data directory"
set -euo pipefail

PORT="${CHROME_DEBUG_PORT:-9222}"
CHROME_BIN="${CHROME_BIN:-/Applications/Google Chrome.app/Contents/MacOS/Google Chrome}"
SOURCE_PROFILE="${CHROME_USER_DATA_DIR:-$HOME/Library/Application Support/Google/Chrome}"
# Must differ from the default Chrome user-data-dir or debugging is refused.
FLOW_PROFILE="${CHROME_FLOW_USER_DATA_DIR:-$HOME/Library/Application Support/Google/Chrome-FlowAgent}"
LOG_FILE="${TMPDIR:-/tmp}/flow-chrome-debug.log"
FORCE_SYNC="${CHROME_FLOW_REFRESH_LOGIN:-0}"
SKIP_SYNC="${CHROME_FLOW_SKIP_SYNC:-0}"
FORCE_RESTART="${CHROME_FLOW_FORCE_RESTART:-0}"

if [[ ! -x "$CHROME_BIN" ]]; then
  echo "Chrome not found at: $CHROME_BIN" >&2
  exit 1
fi

if curl -s -m 1 "http://127.0.0.1:${PORT}/json/version" >/dev/null 2>&1; then
  if [[ "$FORCE_RESTART" != "1" ]]; then
    echo "Chrome already listening on debugging port ${PORT}."
    exit 0
  fi
  echo "Restarting Chrome so a different Flow profile can attach to port ${PORT}…"
fi

quit_chrome() {
  if pgrep -xq "Google Chrome" 2>/dev/null; then
    echo "Quitting Chrome…"
    osascript -e 'tell application "Google Chrome" to quit' >/dev/null 2>&1 || true
    for _ in $(seq 1 40); do
      if ! pgrep -xq "Google Chrome" 2>/dev/null; then
        break
      fi
      sleep 0.5
    done
    if pgrep -xq "Google Chrome" 2>/dev/null; then
      pkill -9 "Google Chrome" 2>/dev/null || true
      sleep 1
    fi
  fi
  rm -f "${SOURCE_PROFILE}/SingletonLock" \
        "${SOURCE_PROFILE}/SingletonSocket" \
        "${SOURCE_PROFILE}/SingletonCookie" \
        "${FLOW_PROFILE}/SingletonLock" \
        "${FLOW_PROFILE}/SingletonSocket" \
        "${FLOW_PROFILE}/SingletonCookie" 2>/dev/null || true
}

sync_login_profile() {
  mkdir -p "$FLOW_PROFILE"
  if [[ "$SKIP_SYNC" == "1" ]]; then
    echo "Using dedicated Flow Chrome profile (no copy from main Chrome): $FLOW_PROFILE"
    if [[ ! -d "$FLOW_PROFILE/Default" ]]; then
      echo "This profile is empty. Sign into Google Flow in the Chrome window that opens, then re-run."
    fi
    return 0
  fi
  if [[ -d "$FLOW_PROFILE/Default" && "$FORCE_SYNC" != "1" ]]; then
    echo "Using existing Flow agent Chrome profile: $FLOW_PROFILE"
    echo "(Set CHROME_FLOW_REFRESH_LOGIN=1 to re-copy login from your main Chrome.)"
    return 0
  fi
  if [[ ! -d "$SOURCE_PROFILE/Default" ]]; then
    echo "Main Chrome profile not found at: $SOURCE_PROFILE/Default" >&2
    exit 1
  fi
  echo "Copying your Chrome login into Flow agent profile (one-time)…"
  echo "  from: $SOURCE_PROFILE"
  echo "  to:   $FLOW_PROFILE"
  # Exclude bulky caches; keep cookies / login / local storage for Google session.
  rsync -a --delete \
    --exclude='Singleton*' \
    --exclude='Crashpad/***' \
    --exclude='**/Cache/***' \
    --exclude='**/Code Cache/***' \
    --exclude='**/GPUCache/***' \
    --exclude='**/Service Worker/CacheStorage/***' \
    --exclude='**/OptimizationGuide*/***' \
    --exclude='BrowserMetrics*' \
    --exclude='**/File System/***' \
    "$SOURCE_PROFILE/" "$FLOW_PROFILE/"
  echo "Login profile ready."
}

quit_chrome
sync_login_profile

echo "Starting Chrome (Flow agent profile) with debugging on port ${PORT}…"
echo "Profile: $FLOW_PROFILE"
echo "Log: $LOG_FILE"

nohup "$CHROME_BIN" \
  --remote-debugging-port="${PORT}" \
  --remote-allow-origins="*" \
  --user-data-dir="${FLOW_PROFILE}" \
  --profile-directory=Default \
  --no-first-run \
  --no-default-browser-check \
  "${CHROME_FLOW_START_URL:-about:blank}" \
  >"$LOG_FILE" 2>&1 &
CHROME_PID=$!
echo "Chrome PID: $CHROME_PID"

for _ in $(seq 1 60); do
  if curl -s -m 1 "http://127.0.0.1:${PORT}/json/version" >/dev/null 2>&1; then
    echo "Chrome debug ready on http://127.0.0.1:${PORT}"
    curl -s "http://127.0.0.1:${PORT}/json/version"
    echo
    exit 0
  fi
  if ! kill -0 "$CHROME_PID" 2>/dev/null && ! pgrep -xq "Google Chrome" 2>/dev/null; then
    echo "Chrome exited before debugging came up. Last log lines:" >&2
    tail -n 50 "$LOG_FILE" >&2 || true
    exit 1
  fi
  sleep 0.5
done

echo "Timed out waiting for Chrome debugging port ${PORT}." >&2
echo "Last log lines:" >&2
tail -n 50 "$LOG_FILE" >&2 || true
if grep -q "non-default data directory" "$LOG_FILE" 2>/dev/null; then
  echo "Chrome still thinks the profile is default. Use a different CHROME_FLOW_USER_DATA_DIR." >&2
fi
exit 1
