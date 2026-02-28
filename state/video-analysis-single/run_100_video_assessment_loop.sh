#!/usr/bin/env bash
set -euo pipefail

ROOT="/Users/davideby/hyperedit"
PYTHON_BIN="/opt/homebrew/bin/python3"
export PATH="/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin"
RUNNER="$ROOT/state/video-analysis-single/run_cinematic_training_qa_batch10.py"
FINAL_DIR="$ROOT/state/final-analysis"
ALL_FILES="/Volumes/Charlie/hyperedit-video-intel/all_files"
CHANNEL_DOWNLOADS="/Volumes/Charlie/hyperedit-video-intel/channel_downloads"
STATUS_JSON="$ROOT/state/video-analysis-single/status.json"
SLO_STATE="$ROOT/state/video-analysis-single/.queue_slo_state.json"
QUEUE_DEPTH_MIN=4
QUEUE_DEPTH_TARGET=10
LOOP_LOCK_DIR="$ROOT/state/video-analysis-single/.loop_supervisor.lockdir"
if ! mkdir "$LOOP_LOCK_DIR" 2>/dev/null; then
  echo "LOOP_ALREADY_RUNNING"
  exit 0
fi
trap 'rmdir "$LOOP_LOCK_DIR" 2>/dev/null || true' EXIT
ASSESS_DIR="$ROOT/state/final-analysis/assessments"
LOCK="$ROOT/state/video-analysis-single/.batch10.lock"
mkdir -p "$ASSESS_DIR"

count_done() {
  find "$FINAL_DIR" -maxdepth 1 -type f -name '*_done.marker' | wc -l | tr -d ' '
}

queue_depth() {
  find "$ALL_FILES" -maxdepth 1 -type f \( -iname '*.mp4' -o -iname '*.mov' -o -iname '*.mkv' -o -iname '*.webm' -o -iname '*.m4v' \) | wc -l | tr -d ' '
}

disk_free_gb() {
  local target="$1"
  df -g "$target" | awk 'NR==2{print $4+0}'
}

lock_state() {
  if [ ! -f "$LOCK" ]; then echo "none"; return; fi
  local pid
  pid=$(tr -d '\n' < "$LOCK" 2>/dev/null || true)
  if [[ "$pid" =~ ^[0-9]+$ ]] && kill -0 "$pid" 2>/dev/null; then
    echo "live:$pid"
  else
    echo "stale"
  fi
}

clear_stale_lock() {
  if [ "$(lock_state)" = "stale" ]; then
    rm -f "$LOCK" || true
  fi
}

restage_to_target() {
  "$PYTHON_BIN" - <<'PY'
from pathlib import Path
import shutil
ALL=Path('/Volumes/Charlie/hyperedit-video-intel/all_files')
DL=Path('/Volumes/Charlie/hyperedit-video-intel/channel_downloads')
DONE=Path('/Volumes/Charlie/hyperedit-video-intel/done')
TARGET=10
exts={'.mp4','.mov','.mkv','.webm','.m4v'}
ALL.mkdir(parents=True, exist_ok=True)
def vids(d):
    return sorted([p for p in d.iterdir() if p.is_file() and p.suffix.lower() in exts])
current=vids(ALL)
if len(current)>=TARGET:
    print('RESTAGE_SKIPPED depth',len(current)); raise SystemExit(0)
need=TARGET-len(current)
cands=[p for p in vids(DL) if not (ALL/p.name).exists() and not (DONE/p.name).exists()]
for src in cands[:need]:
    shutil.copy2(src, ALL/src.name)
print('RESTAGED', min(need,len(cands)))
PY
}

write_status() {
  local action_taken="$1"
  local qd="$2"
  local below="$3"
  local lstate="$4"
  local worker_active="$5"
  local root_free charlie_free
  root_free=$(disk_free_gb "/")
  charlie_free=$(disk_free_gb "/Volumes/Charlie")
  "$PYTHON_BIN" - <<PY
import json,datetime,os
p=os.path.expanduser('$STATUS_JSON')
os.makedirs(os.path.dirname(p), exist_ok=True)
obj={
  'timestamp': datetime.datetime.now().astimezone().isoformat(),
  'queue_depth': int('$qd'),
  'queue_depth_min': int('$QUEUE_DEPTH_MIN'),
  'below_threshold_consecutive': int('$below'),
  'lock_state': '$lstate',
  'disk_free_root_gb': int('$root_free'),
  'disk_free_charlie_gb': int('$charlie_free'),
  'worker_active': bool(int('$worker_active')),
  'action_taken': '$action_taken'
}
with open(p,'w') as f: json.dump(obj,f,indent=2)
print(p)
PY
}

load_below_counter() {
  if [ -f "$SLO_STATE" ]; then
    "$PYTHON_BIN" - <<PY
import json
try:
  print(int(json.load(open('$SLO_STATE')).get('below',0)))
except Exception:
  print(0)
PY
  else
    echo 0
  fi
}

save_below_counter() {
  local n="$1"
  "$PYTHON_BIN" - <<PY
import json,os
os.makedirs(os.path.dirname('$SLO_STATE'), exist_ok=True)
json.dump({'below': int('$n')}, open('$SLO_STATE','w'))
PY
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

START_DONE=$(count_done)
TARGET_DONE=$(( START_DONE + 100 ))
NEXT_ASSESS=$(( (START_DONE/20) + 1 ))

echo "LOOP_START done=$START_DONE target=$TARGET_DONE"

while true; do
  done_now=$(count_done)
  qd=$(queue_depth)
  below=$(load_below_counter)
  action="none"

  if [ "$qd" -lt "$QUEUE_DEPTH_MIN" ]; then
    below=$((below+1))
  else
    below=0
  fi

  if [ "$below" -ge 2 ]; then
    restage_to_target || true
    qd=$(queue_depth)
    action="restage"
    below=0
  fi
  save_below_counter "$below"

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

  worker_active=0
  if pgrep -f "run_cinematic_training_qa_batch10.py" >/dev/null; then
    worker_active=1
  fi

  lstate=$(lock_state)
  write_status "$action" "$qd" "$below" "$lstate" "$worker_active" >/dev/null || true

  if [ "$worker_active" -eq 1 ]; then
    sleep 30
    continue
  fi

  clear_stale_lock
  echo "START_BATCH done=$done_now qd=$qd"
  (
    cd "$ROOT"
    export VISION_MODEL_11B='mlx-community/llama-3.2-11b-vision-instruct'
    PYTHONUNBUFFERED=1 "$PYTHON_BIN" "$RUNNER"
  ) || true
  sleep 5

done

echo "LOOP_COMPLETE"
