#!/usr/bin/env bash
set -euo pipefail

ROOT="/Users/davideby/hyperedit"
PYTHON_BIN="/opt/homebrew/bin/python3"
export PATH="/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin"
RUNNER="$ROOT/state/video-analysis-single/run_cinematic_training_qa_batch10.py"
FINAL_DIR="$ROOT/state/final-analysis"
ALL_FILES="/Volumes/Charlie/hyperedit-video-intel/all_files"
CHANNEL_DOWNLOADS="/Volumes/Charlie/hyperedit-video-intel/channel_downloads"
DONE_FILES="/Volumes/Charlie/hyperedit-video-intel/done"
NEXT_CANDIDATES="$ROOT/state/video-analysis-single/next_batch10_candidate_list.txt"
STAGED_CANDIDATES="$ROOT/state/video-analysis-single/staged_batch10_candidate_list.txt"
STATUS_JSON="$ROOT/state/video-analysis-single/status.json"
CONTROL_POLICY="$ROOT/state/video-analysis-single/control_pane_policy.py"
LOG_DIR="$ROOT/state/video-analysis-single/logs"
CONTROL_LOG="$LOG_DIR/control-pane.log"
QUEUE_DEPTH_MIN=4
QUEUE_DEPTH_TARGET=10
BELOW_THRESHOLD_LIMIT=2
DISK_THRESHOLD_ROOT_GB=5
DISK_THRESHOLD_CHARLIE_GB=25
LOOP_LOCK_DIR="$ROOT/state/video-analysis-single/.loop_supervisor.lockdir"
if ! mkdir "$LOOP_LOCK_DIR" 2>/dev/null; then
  echo "LOOP_ALREADY_RUNNING"
  exit 0
fi
trap 'rmdir "$LOOP_LOCK_DIR" 2>/dev/null || true' EXIT
ASSESS_DIR="$ROOT/state/final-analysis/assessments"
LOCK="$ROOT/state/video-analysis-single/.batch10.lock"
mkdir -p "$ASSESS_DIR" "$LOG_DIR"

count_done() {
  find "$FINAL_DIR" -maxdepth 1 -type f -name '*_done.marker' | wc -l | tr -d ' '
}

queue_depth() {
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

lock_state() {
  if [ ! -f "$LOCK" ]; then echo "none"; return 0; fi
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
    # PID is alive but no longer owned by the batch runner; treat lock as stale.
    echo "stale:pid_reused:$pid"
  fi
}

restage_to_target() {
  ALL_FILES_ENV="$ALL_FILES" \
  CHANNEL_DOWNLOADS_ENV="$CHANNEL_DOWNLOADS" \
  DONE_FILES_ENV="$DONE_FILES" \
  NEXT_CANDIDATES_ENV="$NEXT_CANDIDATES" \
  STAGED_CANDIDATES_ENV="$STAGED_CANDIDATES" \
  QUEUE_DEPTH_TARGET_ENV="$QUEUE_DEPTH_TARGET" \
  "$PYTHON_BIN" - <<'PY'
from pathlib import Path
import os
import shutil
import re
ALL=Path(os.environ['ALL_FILES_ENV'])
DL=Path(os.environ['CHANNEL_DOWNLOADS_ENV'])
DONE=Path(os.environ['DONE_FILES_ENV'])
NEXT=Path(os.environ['NEXT_CANDIDATES_ENV'])
STAGED=Path(os.environ['STAGED_CANDIDATES_ENV'])
TARGET=int(os.environ['QUEUE_DEPTH_TARGET_ENV'])
exts={'.mp4','.mov','.mkv','.webm','.m4v'}
ALL.mkdir(parents=True, exist_ok=True)
def vids(d: Path):
    if not d.exists():
        return []
    return sorted([p for p in d.iterdir() if p.is_file() and p.suffix.lower() in exts])
def read_candidates(path: Path):
    if not path.exists():
        return []
    out=[]
    for line in path.read_text(errors='ignore').splitlines():
        line=line.strip()
        if line and not line.startswith('#'):
            out.append(Path(line))
    return out
def resolve_variant(path: Path):
    if path.exists():
        return path
    stem=path.stem
    m=re.match(r'^(?P<base>.+)\.f(?:137|247|399)$', stem) or re.match(r'^(?P<base>.+)\.f\d+$', stem)
    if m:
        canonical=path.with_name(m.group('base') + '.mp4')
        if canonical.exists():
            return canonical
    if path.suffix.lower() != '.mp4':
        canonical=path.with_suffix('.mp4')
        if canonical.exists():
            return canonical
    return None
current=vids(ALL)
if len(current)>=TARGET:
    print('RESTAGE_SKIPPED depth',len(current)); raise SystemExit(0)
need=TARGET-len(current)
queued={p.name for p in current}
sources=read_candidates(NEXT) + read_candidates(STAGED) + vids(DL)
seen=set()
ordered=[]
for src in sorted(sources, key=lambda p: str(p).lower()):
    key=str(src).lower()
    if key in seen:
        continue
    seen.add(key)
    ordered.append(src)
added=0
for raw in ordered:
    src=resolve_variant(raw)
    if not src:
        continue
    if src.name in queued:
        continue
    if (DONE/src.name).exists():
        continue
    dst=ALL/src.name
    try:
        shutil.copy2(src, dst)
    except Exception:
        continue
    queued.add(src.name)
    added += 1
    if len(queued) >= TARGET:
        break
print('RESTAGED', added, 'NEEDED', need, 'QUEUE', len(queued))
PY
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

run_assessment() {
  local idx="$1"
  "$PYTHON_BIN" - "$idx" <<'PY'
import sys, re
from pathlib import Path
from collections import Counter
idx=int(sys.argv[1])
root=Path('/Users/davideby/hyperedit/state/final-analysis')
assess=root/'assessments'
assess.mkdir(parents=True, exist_ok=True)
reports=sorted(root.glob('*_final_synthesis.md'), key=lambda p:p.stat().st_mtime, reverse=True)[:20]
text='\n'.join(p.read_text(errors='ignore') for p in reports)
lines=text.lower()

themes={
 'composition':['leading lines','symmetry','framing','depth','wide','close','composition'],
 'motion':['dolly','pan','tilt','orbit','handheld','movement','static'],
 'pacing':['hook','rehook','tempo','pacing','transition','shot duration'],
 'audio':['bpm','music','sound design','onset','energy','brightness'],
 'real_estate_features':['kitchen','living','bedroom','bathroom','exterior','pool','fireplace','vaulted']
}
score=[]
for k,words in themes.items():
    c=sum(lines.count(w) for w in words)
    score.append((k,c))
score.sort(key=lambda x:x[1], reverse=True)

words=[w for w in re.findall(r"[a-z']+", lines) if len(w)>3]
bi=Counter(' '.join(words[i:i+2]) for i in range(len(words)-1))
tri=Counter(' '.join(words[i:i+3]) for i in range(len(words)-2))

out=assess/f'assessment_{idx:02d}.md'
md=[f"# Comprehensive Assessment {idx}", "", f"Analyzed {len(reports)} most-recent final synthesis reports.", "", "## Top Overarching Themes"]
for k,c in score:
    md.append(f"- {k}: {c} mentions")
md += ["", "## Recurring Pattern Signals (bigrams)"]
for p,c in bi.most_common(20):
    md.append(f"- {p}: {c}")
md += ["", "## Recurring Pattern Signals (trigrams)"]
for p,c in tri.most_common(15):
    md.append(f"- {p}: {c}")
md += ["", "## Working Rules / Guidelines Draft", "- Keep first hook window tight and visual.", "- Favor coherent motion continuity over hyper-fragmented cuts.", "- Align music cueing with transition accents and room/amenity reveals.", "- Preserve semantic coverage of premium amenities in early/mid timeline.", "- Maintain deterministic tags for shot type, focal estimate, and spatial layers."]
out.write_text('\n'.join(md))
print(out)
PY
}

run_meta_assessment() {
  "$PYTHON_BIN" - <<'PY'
from pathlib import Path
from collections import Counter
import re
assess_dir=Path('/Users/davideby/hyperedit/state/final-analysis/assessments')
files=sorted(assess_dir.glob('assessment_*.md'))[:5]
text='\n'.join(f.read_text(errors='ignore').lower() for f in files)
counts=Counter(re.findall(r'[a-z_]{4,}', text))
out=assess_dir/'assessment_meta_5x.md'
md=['# Meta Assessment Across 5 Comprehensive Assessments','',f'Sources: {len(files)} assessment files','', '## Strongest Repeating Themes']
for k,v in counts.most_common(40):
    md.append(f'- {k}: {v}')
md += ['', '## Consolidated Rule Set', '- 8B remains production core; use higher-tier refinement selectively.', '- Keep one vision instance active at all times.', '- Use fallback ladder 11B → 8B → 4B with checkpoint restart.', '- Standardize schema provenance (`vision_model_used`, `vision_fallback_chain`).', '- Optimize for stable throughput and deterministic comparative analysis.']
out.write_text('\n'.join(md))
print(out)
PY
}

ensure_status_file

START_DONE=$(count_done)
TARGET_DONE=$(( START_DONE + 100 ))
NEXT_ASSESS=$(( (START_DONE/20) + 1 ))

echo "LOOP_START done=$START_DONE target=$TARGET_DONE"

while true; do
  done_now=$(count_done)
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

  # every 20 completed markers, create one comprehensive assessment
  while [ "$done_now" -ge $(( NEXT_ASSESS*20 )) ] && [ "$NEXT_ASSESS" -le 5 ]; do
    echo "ASSESSMENT_TRIGGER idx=$NEXT_ASSESS done=$done_now"
    run_assessment "$NEXT_ASSESS" || true
    NEXT_ASSESS=$((NEXT_ASSESS+1))
  done

  if [ "$done_now" -ge "$TARGET_DONE" ] && [ "$NEXT_ASSESS" -gt 5 ]; then
    echo "TARGET_REACHED done=$done_now"
    run_meta_assessment || true
    break
  fi

  decision=$(policy_action)
  action="${decision%%$'\t'*}"
  reason="${decision#*$'\t'}"
  if [ "$reason" = "$decision" ]; then
    reason="policy_parse_error"
  fi

  case "$action" in
    restage_queue)
      echo "ALERT_QUEUE_SLO queue_depth=$qd min=$QUEUE_DEPTH_MIN consecutive=$below action=restage_queue"
      restage_to_target || true
      qd=$(queue_depth)
      below=0
      worker_active=0
      if pgrep -f "run_cinematic_training_qa_batch10.py" >/dev/null; then
        worker_active=1
      fi
      lstate=$(lock_state)
      root_free=$(disk_free_gb "$ROOT")
      charlie_free=$(disk_free_gb "/Volumes/Charlie")
      write_status "$action" "$reason" "$qd" "$below" "$lstate" "$worker_active" "$root_free" "$charlie_free" >/dev/null || true
      log_control_action "loop" "$action" "$reason" "$qd" "$below" "$lstate" "$worker_active" "$root_free" "$charlie_free"
      sleep 5
      ;;
    clear_stale_lock)
      rm -f "$LOCK" || true
      lstate=$(lock_state)
      root_free=$(disk_free_gb "$ROOT")
      charlie_free=$(disk_free_gb "/Volumes/Charlie")
      write_status "$action" "$reason" "$qd" "$below" "$lstate" "$worker_active" "$root_free" "$charlie_free" >/dev/null || true
      log_control_action "loop" "$action" "$reason" "$qd" "$below" "$lstate" "$worker_active" "$root_free" "$charlie_free"
      sleep 5
      ;;
    ensure_worker)
      write_status "$action" "$reason" "$qd" "$below" "$lstate" 1 "$root_free" "$charlie_free" >/dev/null || true
      log_control_action "loop" "$action" "$reason" "$qd" "$below" "$lstate" 1 "$root_free" "$charlie_free"
      echo "START_BATCH done=$done_now qd=$qd"
      (
        cd "$ROOT"
        export VISION_MODEL_11B='mlx-community/llama-3.2-11b-vision-instruct'
        PYTHONUNBUFFERED=1 "$PYTHON_BIN" "$RUNNER"
      ) || true
      sleep 5
      ;;
    no_op)
      write_status "$action" "$reason" "$qd" "$below" "$lstate" "$worker_active" "$root_free" "$charlie_free" >/dev/null || true
      if [[ "$reason" == disk_low* || "$reason" == live_lock_present ]]; then
        log_control_action "loop" "$action" "$reason" "$qd" "$below" "$lstate" "$worker_active" "$root_free" "$charlie_free"
      fi
      sleep 30
      ;;
    *)
      write_status "no_op" "unknown_action" "$qd" "$below" "$lstate" "$worker_active" "$root_free" "$charlie_free" >/dev/null || true
      log_control_action "loop" "no_op" "unknown_action" "$qd" "$below" "$lstate" "$worker_active" "$root_free" "$charlie_free"
      sleep 30
      ;;
  esac
done

echo "LOOP_COMPLETE"
