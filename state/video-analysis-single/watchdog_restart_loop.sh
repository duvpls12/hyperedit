#!/usr/bin/env bash
set -euo pipefail

ROOT="/Users/davideby/hyperedit"
PYTHON_BIN="/opt/homebrew/bin/python3"
export PATH="/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin"
LOOP_SCRIPT="$ROOT/state/video-analysis-single/run_100_video_assessment_loop.sh"
LOCK="$ROOT/state/video-analysis-single/.batch10.lock"
STATUS_JSON="$ROOT/state/video-analysis-single/status.json"
CONTROL_POLICY="$ROOT/state/video-analysis-single/control_pane_policy.py"
ALL_FILES="/Volumes/Charlie/hyperedit-video-intel/all_files"
LOG_DIR="$ROOT/state/video-analysis-single/logs"
CONTROL_LOG="$LOG_DIR/control-pane.log"
QUEUE_DEPTH_MIN=4
QUEUE_DEPTH_TARGET=10
BELOW_THRESHOLD_LIMIT=2
DISK_THRESHOLD_ROOT_GB=5
DISK_THRESHOLD_CHARLIE_GB=25
mkdir -p "$LOG_DIR"

lock_state() {
  if [ ! -f "$LOCK" ]; then
    echo "none"
    return 0
  fi
  local pid
  pid=$(tr -d '\n' < "$LOCK" 2>/dev/null || true)
  if ! [[ "$pid" =~ ^[0-9]+$ ]]; then
    echo "stale:invalid_pid"
    return 0
  fi
  if ! kill -0 "$pid" 2>/dev/null; then
    echo "stale:dead_pid:$pid"
    return 0
  fi
  if ps -p "$pid" -o command= 2>/dev/null | grep -q "run_cinematic_training_qa_batch10.py"; then
    echo "live:$pid"
  else
    echo "stale:pid_reused:$pid"
  fi
}

queue_depth() {
  if [ ! -d "$ALL_FILES" ]; then
    echo 0
    return 0
  fi
  find "$ALL_FILES" -maxdepth 1 -type f \( -iname '*.mp4' -o -iname '*.mov' -o -iname '*.mkv' -o -iname '*.webm' -o -iname '*.m4v' \) | wc -l | tr -d ' '
}

disk_free_gb() {
  local target="$1"
  local free
  free=$(df -g "$target" 2>/dev/null | awk 'NR==2{print $4+0}' || true)
  if [ -z "${free:-}" ]; then
    echo -1
  else
    echo "$free"
  fi
}

log_control_action() {
  local source="$1"
  local action="$2"
  local reason="$3"
  local qd="$4"
  local below="$5"
  local lstate="$6"
  local worker_active="$7"
  local root_free="$8"
  local charlie_free="$9"
  printf '%s source=%s action=%s reason=%s qd=%s below=%s lock=%s worker=%s root_free_gb=%s charlie_free_gb=%s\n' \
    "$(date -u +"%Y-%m-%dT%H:%M:%SZ")" \
    "$source" "$action" "$reason" "$qd" "$below" "$lstate" "$worker_active" "$root_free" "$charlie_free" >> "$CONTROL_LOG"
}

ensure_status_file() {
  "$PYTHON_BIN" - <<PY
import json, os
p = os.path.expanduser('$STATUS_JSON')
if os.path.exists(p):
    raise SystemExit(0)
os.makedirs(os.path.dirname(p), exist_ok=True)
obj = {
  'schema_version': 1,
  'timestamp': '1970-01-01T00:00:00Z',
  'queue_depth': 0,
  'queue_depth_min': int('$QUEUE_DEPTH_MIN'),
  'queue_depth_target': int('$QUEUE_DEPTH_TARGET'),
  'below_threshold_consecutive': 0,
  'below_threshold_limit': int('$BELOW_THRESHOLD_LIMIT'),
  'lock_state': 'none',
  'disk_free_root_gb': -1,
  'disk_free_charlie_gb': -1,
  'disk_threshold_root_gb': int('$DISK_THRESHOLD_ROOT_GB'),
  'disk_threshold_charlie_gb': int('$DISK_THRESHOLD_CHARLIE_GB'),
  'worker_active': False,
  'action_taken': 'no_op',
  'action_reason': 'initialized'
}
with open(p, 'w') as f:
    json.dump(obj, f, indent=2)
PY
}

load_below_counter() {
  "$PYTHON_BIN" - <<PY
import json
try:
  data = json.load(open('$STATUS_JSON'))
  print(int(data.get('below_threshold_consecutive', 0)))
except Exception:
  print(0)
PY
}

write_status() {
  local action_taken="$1"
  local action_reason="$2"
  local qd="$3"
  local below="$4"
  local lstate="$5"
  local worker_active="$6"
  local root_free="$7"
  local charlie_free="$8"
  "$PYTHON_BIN" - <<PY
import json, datetime, os
p = os.path.expanduser('$STATUS_JSON')
os.makedirs(os.path.dirname(p), exist_ok=True)
obj = {}
try:
  loaded = json.load(open(p))
  if isinstance(loaded, dict):
    obj = loaded
except Exception:
  obj = {}
obj.update({
  'schema_version': 1,
  'timestamp': datetime.datetime.now().astimezone().isoformat(),
  'queue_depth': int('$qd'),
  'queue_depth_min': int('$QUEUE_DEPTH_MIN'),
  'queue_depth_target': int('$QUEUE_DEPTH_TARGET'),
  'below_threshold_consecutive': int('$below'),
  'below_threshold_limit': int('$BELOW_THRESHOLD_LIMIT'),
  'lock_state': '$lstate',
  'disk_free_root_gb': int('$root_free'),
  'disk_free_charlie_gb': int('$charlie_free'),
  'disk_threshold_root_gb': int('$DISK_THRESHOLD_ROOT_GB'),
  'disk_threshold_charlie_gb': int('$DISK_THRESHOLD_CHARLIE_GB'),
  'worker_active': bool(int('$worker_active')),
  'action_taken': '$action_taken',
  'action_reason': '$action_reason'
})
with open(p, 'w') as f:
  json.dump(obj, f, indent=2)
print(p)
PY
}

policy_action() {
  if [ ! -f "$CONTROL_POLICY" ]; then
    echo $'no_op\tpolicy_missing'
    return 0
  fi
  "$PYTHON_BIN" "$CONTROL_POLICY" --status "$STATUS_JSON" 2>/dev/null || echo $'no_op\tpolicy_error'
}

launch_loop() {
  local ts
  ts=$(date +"%Y%m%d-%H%M%S")
  nohup bash "$LOOP_SCRIPT" >> "$LOG_DIR/loop-$ts.log" 2>&1 &
}

ensure_status_file

while true; do
  if ! pgrep -f "run_100_video_assessment_loop.sh" >/dev/null; then
    qd=$(queue_depth)
    below=$(load_below_counter)
    if [ "$qd" -lt "$QUEUE_DEPTH_MIN" ]; then
      below=$((below+1))
    else
      below=0
    fi

    worker_active=0
    if pgrep -f "run_cinematic_training_qa_batch10.py" >/dev/null; then
      worker_active=1
    fi

    lstate=$(lock_state)
    root_free=$(disk_free_gb "$ROOT")
    charlie_free=$(disk_free_gb "/Volumes/Charlie")

    write_status "no_op" "policy_pending" "$qd" "$below" "$lstate" "$worker_active" "$root_free" "$charlie_free" >/dev/null || true

    decision=$(policy_action)
    action="${decision%%$'\t'*}"
    reason="${decision#*$'\t'}"
    if [ "$reason" = "$decision" ]; then
      action="no_op"
      reason="policy_parse_error"
    fi

    if [ "$action" = "clear_stale_lock" ]; then
      rm -f "$LOCK" || true
      lstate=$(lock_state)
      write_status "$action" "$reason" "$qd" "$below" "$lstate" "$worker_active" "$root_free" "$charlie_free" >/dev/null || true
      log_control_action "watchdog" "$action" "$reason" "$qd" "$below" "$lstate" "$worker_active" "$root_free" "$charlie_free"

      write_status "no_op" "policy_pending" "$qd" "$below" "$lstate" "$worker_active" "$root_free" "$charlie_free" >/dev/null || true
      decision=$(policy_action)
      action="${decision%%$'\t'*}"
      reason="${decision#*$'\t'}"
      if [ "$reason" = "$decision" ]; then
        action="no_op"
        reason="policy_parse_error"
      fi
    fi

    case "$action" in
      ensure_worker|restage_queue)
        write_status "$action" "$reason" "$qd" "$below" "$lstate" 1 "$root_free" "$charlie_free" >/dev/null || true
        log_control_action "watchdog" "$action" "$reason" "$qd" "$below" "$lstate" 1 "$root_free" "$charlie_free"
        launch_loop
        ;;
      no_op)
        write_status "$action" "$reason" "$qd" "$below" "$lstate" "$worker_active" "$root_free" "$charlie_free" >/dev/null || true
        if [[ "$reason" == disk_low* || "$reason" == live_lock_present ]]; then
          log_control_action "watchdog" "$action" "$reason" "$qd" "$below" "$lstate" "$worker_active" "$root_free" "$charlie_free"
        fi
        ;;
      *)
        write_status "no_op" "unknown_action" "$qd" "$below" "$lstate" "$worker_active" "$root_free" "$charlie_free" >/dev/null || true
        log_control_action "watchdog" "no_op" "unknown_action" "$qd" "$below" "$lstate" "$worker_active" "$root_free" "$charlie_free"
        ;;
    esac
  fi

  sleep 20
done
