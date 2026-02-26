#!/usr/bin/env python3
"""
Comprehensive corpus analysis of all good vision_pass1.json and final_synthesis.md files.
Outputs aggregated stats to stdout and writes intel markdown files to state/intel/.
"""
import json, re, os, sys
from pathlib import Path
from collections import Counter, defaultdict

ANALYSIS_DIR = Path("state/video-analysis-single")
SYNTHESIS_DIR = Path("state/final-analysis")
INTEL_DIR = Path("state/intel")
INTEL_DIR.mkdir(parents=True, exist_ok=True)


# ───────────────────────────────────────────────
# Helpers
# ───────────────────────────────────────────────
def parse_analysis(a):
    if isinstance(a, dict):
        return a
    if isinstance(a, str):
        # Strip markdown code fences (```json ... ```)
        stripped = a.strip()
        stripped = re.sub(r"^```[a-zA-Z]*\s*", "", stripped)
        stripped = re.sub(r"```\s*$", "", stripped.strip())
        try:
            return json.loads(stripped)
        except Exception:
            return None
    return None


def pct(n, total):
    return f"{n/total*100:.1f}%" if total else "0%"


# ───────────────────────────────────────────────
# 1. Load all good pass1 frames
# ───────────────────────────────────────────────
all_frames = []
good_pass1_files = []
video_frame_map = {}   # video_name -> [frames]

for p in sorted(ANALYSIS_DIR.glob("*_vision_pass1.json")):
    try:
        data = json.loads(p.read_text())
    except Exception:
        continue
    pf = data.get("per_frame", [])
    if not pf:
        continue

    video_name = p.stem.replace("_vision_pass1", "")
    good = []
    for frame in pf:
        a = parse_analysis(frame.get("analysis", ""))
        if a and "error" not in a and a.get("camera_movement") is not None:
            a["_t"] = frame.get("t", 0)
            good.append(a)

    if good:
        good_pass1_files.append(p.name)
        all_frames.extend(good)
        video_frame_map[video_name] = good

print(f"Good pass1 files: {len(good_pass1_files)}")
print(f"Total good frames: {len(all_frames)}")
N = len(all_frames)


# ───────────────────────────────────────────────
# 2. Aggregate counters (frame-level)
# ───────────────────────────────────────────────
cam_movement = Counter()
room_amenity  = Counter()
composition   = Counter()
color_grade   = Counter()
shot_type     = Counter()
seq_role      = Counter()
typo_frames   = 0

for fr in all_frames:
    cam_movement[(fr.get("camera_movement") or "unknown").lower().strip()] += 1
    rm = fr.get("room_or_amenity") or fr.get("room") or "unknown"
    if not isinstance(rm, str):
        rm = "unknown"
    room_amenity[rm.lower().strip()] += 1
    composition[(fr.get("composition") or "unknown").lower().strip()] += 1
    color_grade[(fr.get("color_grade") or "unknown").lower().strip()] += 1
    shot_type[(fr.get("shot_type") or "unknown").lower().strip()] += 1
    seq_role[(fr.get("sequence_role") or "unknown").lower().strip()] += 1
    if fr.get("typography_present") is True:
        typo_frames += 1


# ───────────────────────────────────────────────
# 3. Parse synthesis .md files
# ───────────────────────────────────────────────
synthesis_files = sorted(SYNTHESIS_DIR.glob("*_final_synthesis.md"))
print(f"\nSynthesis .md files: {len(synthesis_files)}")

scores_overall = []
scores_hook = []
scores_rehook = []
scores_motion = []
scores_tension = []
scores_viral = []
scores_music = []

shot_counts = []
avg_durations = []
pacing_labels = []

room_coverage_agg = Counter()  # across all synthesis files
color_agg_synth   = Counter()
composition_agg_synth = Counter()
seq_role_agg_synth = Counter()
movement_agg_synth = Counter()

for md_path in synthesis_files:
    txt = md_path.read_text()

    # --- QA Scorecard ---
    def extract_score(pattern, text):
        m = re.search(pattern, text)
        return float(m.group(1)) if m else None

    overall = extract_score(r"Overall:\s*([\d.]+)/100", txt)
    if overall: scores_overall.append(overall)
    hook = extract_score(r"Hook \(0[^)]+\):\s*([\d.]+)", txt)
    if hook: scores_hook.append(hook)
    rehook = extract_score(r"Rehook Density:\s*([\d.]+)", txt)
    if rehook: scores_rehook.append(rehook)
    motion = extract_score(r"Motion Continuity:\s*([\d.]+)", txt)
    if motion: scores_motion.append(motion)
    tension = extract_score(r"Tension Waveform:\s*([\d.]+)", txt)
    if tension: scores_tension.append(tension)
    viral = extract_score(r"Viral Readiness:\s*([\d.]+)", txt)
    if viral: scores_viral.append(viral)
    music = extract_score(r"Music-Property Match:\s*([\d.]+)", txt)
    if music: scores_music.append(music)

    # --- Shot count / duration ---
    m = re.search(r"Shot count:\s*\*\*(\d+)\*\*", txt)
    if m: shot_counts.append(int(m.group(1)))
    m = re.search(r"avg\s+([\d.]+)s", txt)
    if m: avg_durations.append(float(m.group(1)))

    # --- Room/amenity coverage from synthesis ---
    in_room = False
    for line in txt.splitlines():
        if "## Room/Amenity Coverage" in line:
            in_room = True
            continue
        if in_room:
            if line.startswith("##"):
                break
            m = re.match(r"[-*]?\s*(\w[\w/ ]+):\s*(\d+)\s*frames?", line.strip())
            if m:
                room_coverage_agg[m.group(1).lower().strip()] += int(m.group(2))

    # --- Composition from synthesis ---
    in_comp = False
    for line in txt.splitlines():
        if "## Composition" in line:
            in_comp = True
            continue
        if in_comp:
            if line.startswith("##"):
                break
            m = re.match(r"[-*]?\s*(\w[\w/ ]+):\s*(\d+)\s*frames?", line.strip())
            if m:
                composition_agg_synth[m.group(1).lower().strip()] += int(m.group(2))

    # --- Color/Grade from synthesis ---
    in_col = False
    for line in txt.splitlines():
        if "## Color/Grade" in line:
            in_col = True
            continue
        if in_col:
            if line.startswith("##"):
                break
            m = re.match(r"[-*]?\s*(\w[\w/ ]+):\s*(\d+)\s*frames?", line.strip())
            if m:
                color_agg_synth[m.group(1).lower().strip()] += int(m.group(2))

    # --- Sequence Role from synthesis ---
    in_seq = False
    for line in txt.splitlines():
        if "## Sequence Role" in line:
            in_seq = True
            continue
        if in_seq:
            if line.startswith("##"):
                break
            m = re.match(r"[-*]?\s*(\w[\w/ ]+):\s*(\d+)\s*frames?", line.strip())
            if m:
                seq_role_agg_synth[m.group(1).lower().strip()] += int(m.group(2))

    # --- Movement mix ---
    m = re.search(r"Movement mix:\s*\*\*([^*]+)\*\*", txt)
    if m:
        for part in m.group(1).split(","):
            kv = part.strip().split("=")
            if len(kv) == 2:
                movement_agg_synth[kv[0].strip().lower()] += int(kv[1].strip())


# ───────────────────────────────────────────────
# 4. Print summary tables
# ───────────────────────────────────────────────
def avg(lst): return sum(lst)/len(lst) if lst else 0

print("\n" + "="*60)
print("PASS1 FRAME-LEVEL ANALYSIS")
print("="*60)

print(f"\n── CAMERA MOVEMENT (top 25 / {N} frames) ──")
for k, v in cam_movement.most_common(25):
    print(f"  {k:<35} {v:4d}  {pct(v,N)}")

print(f"\n── ROOM / AMENITY (top 25) ──")
for k, v in room_amenity.most_common(25):
    print(f"  {k:<35} {v:4d}  {pct(v,N)}")

print(f"\n── SHOT TYPE (top 20) ──")
for k, v in shot_type.most_common(20):
    print(f"  {k:<35} {v:4d}  {pct(v,N)}")

print(f"\n── COMPOSITION (top 20) ──")
for k, v in composition.most_common(20):
    print(f"  {k:<35} {v:4d}  {pct(v,N)}")

print(f"\n── COLOR GRADE (top 20) ──")
for k, v in color_grade.most_common(20):
    print(f"  {k:<35} {v:4d}  {pct(v,N)}")

print(f"\n── SEQUENCE ROLE (top 20) ──")
for k, v in seq_role.most_common(20):
    print(f"  {k:<35} {v:4d}  {pct(v,N)}")

print(f"\n── TYPOGRAPHY ──")
print(f"  Frames with text overlay: {typo_frames} / {N} ({pct(typo_frames,N)})")

print("\n" + "="*60)
print("SYNTHESIS FILE ANALYSIS")
print("="*60)

print(f"\n── QA SCORECARD AVERAGES (n={len(scores_overall)}) ──")
print(f"  Overall:          {avg(scores_overall):.1f}")
print(f"  Hook (0-3s):      {avg(scores_hook):.1f}")
print(f"  Rehook Density:   {avg(scores_rehook):.1f}")
print(f"  Motion Continuity:{avg(scores_motion):.1f}")
print(f"  Tension Waveform: {avg(scores_tension):.1f}")
print(f"  Viral Readiness:  {avg(scores_viral):.1f}")
print(f"  Music Match:      {avg(scores_music):.1f}")

print(f"\n── SHOT STATS ──")
print(f"  Avg shot count:        {avg(shot_counts):.0f} shots")
print(f"  Avg shot duration:     {avg(avg_durations):.2f}s")

print(f"\n── ROOM COVERAGE (synthesis, top 20) ──")
total_room = sum(room_coverage_agg.values())
for k, v in room_coverage_agg.most_common(20):
    print(f"  {k:<35} {v:5d}  {pct(v,total_room)}")

print(f"\n── COMPOSITION (synthesis, top 15) ──")
total_comp = sum(composition_agg_synth.values())
for k, v in composition_agg_synth.most_common(15):
    print(f"  {k:<35} {v:5d}  {pct(v,total_comp)}")

print(f"\n── COLOR/GRADE (synthesis, top 15) ──")
total_col = sum(color_agg_synth.values())
for k, v in color_agg_synth.most_common(15):
    print(f"  {k:<35} {v:5d}  {pct(v,total_col)}")

print(f"\n── SEQUENCE ROLE (synthesis, top 15) ──")
total_seq = sum(seq_role_agg_synth.values())
for k, v in seq_role_agg_synth.most_common(15):
    print(f"  {k:<35} {v:5d}  {pct(v,total_seq)}")

print(f"\n── MOVEMENT MIX (synthesis aggregate) ──")
total_mv = sum(movement_agg_synth.values())
for k, v in movement_agg_synth.most_common():
    print(f"  {k:<35} {v:5d}  {pct(v,total_mv)}")


# ───────────────────────────────────────────────
# 5. Per-video stats
# ───────────────────────────────────────────────
print("\n" + "="*60)
print("PER-VIDEO STATS")
print("="*60)
for video, frames in sorted(video_frame_map.items()):
    vc = Counter((f.get("camera_movement") or "unknown").lower() for f in frames)
    vr = Counter((f.get("room_or_amenity") or "unknown").lower() for f in frames if isinstance(f.get("room_or_amenity"), str))
    top_mv = vc.most_common(3)
    top_rm = vr.most_common(3)
    print(f"\n  {video}")
    print(f"    frames: {len(frames)}")
    print(f"    top movements: {', '.join(f'{k}({v})' for k,v in top_mv)}")
    print(f"    top rooms: {', '.join(f'{k}({v})' for k,v in top_rm)}")

# ───────────────────────────────────────────────
# 6. Store raw data as JSON for RAG/markdown generation
# ───────────────────────────────────────────────
corpus_data = {
    "pass1": {
        "total_good_frames": N,
        "good_file_count": len(good_pass1_files),
        "camera_movement": dict(cam_movement.most_common()),
        "room_amenity": dict(room_amenity.most_common()),
        "shot_type": dict(shot_type.most_common()),
        "composition": dict(composition.most_common()),
        "color_grade": dict(color_grade.most_common()),
        "sequence_role": dict(seq_role.most_common()),
        "typography_pct": round(typo_frames/N*100, 1),
    },
    "synthesis": {
        "file_count": len(synthesis_files),
        "qa_scores": {
            "overall_avg": round(avg(scores_overall), 1),
            "hook_avg": round(avg(scores_hook), 1),
            "rehook_avg": round(avg(scores_rehook), 1),
            "motion_continuity_avg": round(avg(scores_motion), 1),
            "tension_waveform_avg": round(avg(scores_tension), 1),
            "viral_readiness_avg": round(avg(scores_viral), 1),
            "music_match_avg": round(avg(scores_music), 1),
        },
        "shot_stats": {
            "avg_shot_count": round(avg(shot_counts), 0),
            "avg_shot_duration_s": round(avg(avg_durations), 2),
        },
        "room_coverage": dict(room_coverage_agg.most_common()),
        "composition": dict(composition_agg_synth.most_common()),
        "color_grade": dict(color_agg_synth.most_common()),
        "sequence_role": dict(seq_role_agg_synth.most_common()),
        "movement_mix": dict(movement_agg_synth.most_common()),
    }
}

out_json = INTEL_DIR / "corpus_stats.json"
out_json.write_text(json.dumps(corpus_data, indent=2))
print(f"\n✓ Saved corpus_stats.json to {out_json}")
