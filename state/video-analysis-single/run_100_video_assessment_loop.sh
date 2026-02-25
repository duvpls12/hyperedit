#!/usr/bin/env bash
set -euo pipefail

ROOT="/Users/davideby/hyperedit"
RUNNER="$ROOT/state/video-analysis-single/run_cinematic_training_qa_batch10.py"
FINAL_DIR="$ROOT/state/final-analysis"
ASSESS_DIR="$ROOT/state/final-analysis/assessments"
LOCK="$ROOT/state/video-analysis-single/.batch10.lock"
mkdir -p "$ASSESS_DIR"

count_done() {
  find "$FINAL_DIR" -maxdepth 1 -type f -name '*_done.marker' | wc -l | tr -d ' '
}

run_assessment() {
  local idx="$1"
  python3 - "$idx" <<'PY'
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

# top recurring phrases (2-4 word simple ngrams)
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
  python3 - <<'PY'
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

  if pgrep -f "run_cinematic_training_qa_batch10.py" >/dev/null; then
    sleep 30
    continue
  fi

  rm -f "$LOCK"
  echo "START_BATCH done=$done_now"
  (
    cd "$ROOT"
    export VISION_MODEL_11B='/Users/davideby/.lmstudio/models/leafspark/Llama-3.2-11B-Vision-Instruct-GGUF/Llama-3.2-11B-Vision-Instruct.Q4_K_M.gguf'
    PYTHONUNBUFFERED=1 python3 "$RUNNER"
  ) || true
  sleep 5

done

echo "LOOP_COMPLETE"
