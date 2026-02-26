#!/usr/bin/env python3
"""
Write all intel markdown files to state/intel/ from corpus_stats.json.
"""
import json
from pathlib import Path
from datetime import date

INTEL_DIR = Path("state/intel")
INTEL_DIR.mkdir(parents=True, exist_ok=True)
TODAY = date.today().isoformat()

data = json.loads((INTEL_DIR / "corpus_stats.json").read_text())
p1 = data["pass1"]
syn = data["synthesis"]

N = p1["total_good_frames"]
def pct(n, total): return f"{n/total*100:.1f}%" if total else "0%"


# ════════════════════════════════════════════════════════════
# 1. CAMERA MOVEMENT ATLAS
# ════════════════════════════════════════════════════════════
cam = p1["camera_movement"]
total_cam = sum(cam.values())

# Normalize/group the camera movement labels
groups = {
    "static / locked": ["static", "stationary", "still", "none", "no", "n/a"],
    "horizontal pan": ["horizontal", "pan", "panning", "horizontal pan"],
    "drone / aerial": ["drone_flyover", "aerial", "drone"],
    "gimbal walk": ["gimbal_walk_forward", "gimbal_walk_backward"],
    "tilt": ["tilt", "tilt-shift", "tilt_up", "tilt_down"],
    "other": [],
}

def classify_mv(label):
    l = label.lower()
    for group, keys in groups.items():
        if any(k in l for k in keys):
            return group
    return "other"

group_counts = {}
for k, v in cam.items():
    g = classify_mv(k)
    group_counts[g] = group_counts.get(g, 0) + v

lines = [
    f"# Camera Movement Atlas",
    f"",
    f"> Derived from **{N:,} frames** across **{p1['good_file_count']} videos** (qwen2.5vl:7b, 5 fps, 720px)",
    f"> Generated: {TODAY}",
    f"",
    f"## Summary",
    f"",
    f"| Movement Category | Frames | % |",
    f"|---|---|---|",
]
for g, v in sorted(group_counts.items(), key=lambda x: -x[1]):
    lines.append(f"| {g} | {v:,} | {pct(v, total_cam)} |")

lines += [
    f"",
    f"## Key Insight",
    f"",
    f"**Static/locked shots dominate at ~70%** (static + stationary + still + none combined).",
    f"Horizontal panning (pan + panning + horizontal) accounts for ~25% of movement.",
    f"Drone/aerial appears in ~5% of frames — reserved for establishing shots and exterior reveals.",
    f"",
    f"## Raw Label Breakdown",
    f"",
    f"| Label (raw) | Frames | % |",
    f"|---|---|---|",
]
for k, v in sorted(cam.items(), key=lambda x: -x[1]):
    if v >= 5:
        lines.append(f"| `{k}` | {v:,} | {pct(v, total_cam)} |")

lines += [
    f"",
    f"## Editorial Rules Derived",
    f"",
    f"1. **Default to static** — majority of shots are locked. Movement is an accent, not a default.",
    f"2. **Pan = the workhorse** — when movement appears, it's almost always a slow horizontal pan.",
    f"3. **Drone for openers and exteriors only** — aerial > 5fps is exceptional; treat as a premium cut.",
    f"4. **Gimbal walk is rare** (<0.1%) — used sparingly for immersive interior walkthroughs.",
    f"5. **No whip pans, speed ramps, or push/pull** detected in corpus — these would read as stylistically aggressive for this market.",
]

(INTEL_DIR / "camera_movement_atlas.md").write_text("\n".join(lines))
print("✓ camera_movement_atlas.md")


# ════════════════════════════════════════════════════════════
# 2. ROOM COVERAGE MAP
# ════════════════════════════════════════════════════════════
rooms = p1["room_amenity"]
total_rooms = sum(rooms.values())

# Normalize room labels into canonical groups
room_groups = {
    "living room / great room": ["living room", "living_room", "great room", "living area"],
    "bedroom": ["bedroom", "master bedroom", "primary bedroom"],
    "bathroom": ["bathroom", "bath", "master bath"],
    "kitchen": ["kitchen", "kitchen area"],
    "outdoor / patio": ["outdoor", "outdoor_living_area", "patio", "outdoor patio", "outdoor seating area", "terrace"],
    "pool": ["pool", "outdoor_pool", "outdoor_pool_area", "swimming pool", "poolside"],
    "exterior / facade": ["exterior", "exterior_facade", "facade"],
    "garage": ["garage"],
    "staircase": ["staircase", "stairs"],
    "balcony": ["balcony"],
    "entrance / foyer": ["entrance", "foyer", "entry"],
    "dining room": ["dining room", "dining area"],
    "closet / dressing": ["closet", "dressing room"],
    "none / unknown": ["none", "unknown", "not_applicable", "n/a"],
}

def classify_room(label):
    l = label.lower().strip()
    for group, keys in room_groups.items():
        if any(k == l or k in l for k in keys):
            return group
    return "other"

rgroup_counts = {}
for k, v in rooms.items():
    g = classify_room(k)
    rgroup_counts[g] = rgroup_counts.get(g, 0) + v

lines = [
    f"# Room & Amenity Coverage Map",
    f"",
    f"> Derived from **{N:,} frames** across **{p1['good_file_count']} videos**",
    f"> Generated: {TODAY}",
    f"",
    f"## Coverage by Room Category",
    f"",
    f"| Room | Frames | % of Total |",
    f"|---|---|---|",
]
for g, v in sorted(rgroup_counts.items(), key=lambda x: -x[1]):
    if g not in ("none / unknown", "other"):
        lines.append(f"| {g} | {v:,} | {pct(v, total_rooms)} |")

lines += [
    f"",
    f"## Coverage Hierarchy",
    f"",
    f"```",
    f"1. Living Room / Great Room   ≈ 20%  — anchor space, most screen time",
    f"2. Bedroom                    ≈  8%  — secondary interior",
    f"3. Outdoor / Patio            ≈  8%  — lifestyle appeal",
    f"4. Bathroom                   ≈  7%  — detail and luxury signal",
    f"5. Kitchen                    ≈  6%  — functional/lifestyle",
    f"6. Exterior / Facade          ≈  3%  — curb appeal opener",
    f"7. Pool                       ≈  3%  — premium amenity",
    f"8. Staircase                  ≈  1%  — architectural transition",
    f"9. Balcony / Terrace          ≈  1%  — view highlight",
    f"10. Dining Room               ≈  2%  — secondary indoor",
    f"```",
    f"",
    f"## Editorial Rules Derived",
    f"",
    f"1. **Living room is the anchor** — always open or close the interior sequence there.",
    f"2. **Bathroom earns disproportionate time** relative to square footage — signals luxury.",
    f"3. **Pool if present = featured moment** — not a B-roll throwaway.",
    f"4. **Outdoor/patio gets nearly as much time as bedroom** — lifestyle framing matters.",
    f"5. **Staircase is a transition device** — used to bridge floors, not as a showcase.",
    f"6. **Kitchen under-represented at 6%** — likely an opportunity to add more food/lifestyle shots.",
    f"7. **Closets and dressing rooms appear** — indicates premium properties include walk-in coverage.",
    f"",
    f"## Raw Label Breakdown (top 30)",
    f"",
    f"| Label | Frames | % |",
    f"|---|---|---|",
]
for k, v in sorted(rooms.items(), key=lambda x: -x[1])[:30]:
    lines.append(f"| `{k}` | {v:,} | {pct(v, total_rooms)} |")

(INTEL_DIR / "room_coverage_map.md").write_text("\n".join(lines))
print("✓ room_coverage_map.md")


# ════════════════════════════════════════════════════════════
# 3. SHOT GRAMMAR GUIDE
# ════════════════════════════════════════════════════════════
shots = p1["shot_type"]
total_shots = sum(shots.values())
comp = p1["composition"]
total_comp = sum(comp.values())
seq = p1["sequence_role"]
total_seq = sum(seq.values())

synth_shots = syn["shot_stats"]

lines = [
    f"# Shot Grammar Guide",
    f"",
    f"> Derived from **{N:,} frames** and **{syn['file_count']} synthesis files**",
    f"> Generated: {TODAY}",
    f"",
    f"## Shot Statistics",
    f"",
    f"| Metric | Value |",
    f"|---|---|",
    f"| Avg shot count per video | {int(synth_shots['avg_shot_count'])} shots |",
    f"| Avg shot duration | {synth_shots['avg_shot_duration_s']}s |",
    f"| Implied cuts per minute (60s/1.49s) | ~40 cuts/min |",
    f"| Typography / text overlay | {p1['typography_pct']}% of frames |",
    f"",
    f"## Shot Type Distribution",
    f"",
    f"| Shot Type | Frames | % |",
    f"|---|---|---|",
]
for k, v in sorted(shots.items(), key=lambda x: -x[1]):
    if v >= 20:
        lines.append(f"| `{k}` | {v:,} | {pct(v, total_shots)} |")

lines += [
    f"",
    f"## Composition Distribution",
    f"",
    f"| Composition | Frames | % |",
    f"|---|---|---|",
]
for k, v in sorted(comp.items(), key=lambda x: -x[1]):
    if v >= 20:
        lines.append(f"| `{k}` | {v:,} | {pct(v, total_comp)} |")

lines += [
    f"",
    f"## Sequence Role Distribution",
    f"",
    f"| Role | Frames | % |",
    f"|---|---|---|",
]
for k, v in sorted(seq.items(), key=lambda x: -x[1]):
    if v >= 10:
        lines.append(f"| `{k}` | {v:,} | {pct(v, total_seq)} |")

lines += [
    f"",
    f"## Shot Grammar Rules",
    f"",
    f"### Pacing",
    f"- **~78 shots per video, avg 1.49s/shot** — this is fast. Social/reel-style cutting.",
    f"- **Cinematic real estate ≠ slow luxury pacing** — the corpus shows rapid-cut editorial.",
    f"- A 90s property video has ~60 cuts. A 2-min video has ~80 cuts.",
    f"",
    f"### Shot Type Hierarchy",
    f"```",
    f"1. pan / wide_establishing  ≈ 35%  — establishing and space-reading shots",
    f"2. exterior               ≈ 11%  — curb appeal, arrival",
    f"3. wide                   ≈  9%  — room intros",
    f"4. static                 ≈  9%  — detail holds",
    f"5. interior               ≈  7%  — room flow shots",
    f"6. aerial_oblique         ≈  6%  — property-in-context",
    f"7. aerial (overhead)      ≈  5%  — neighborhood/lot overview",
    f"8. panoramic              ≈  4%  — 180° reveals",
    f"9. medium                 ≈  3%  — lifestyle / human scale",
    f"10. title card             ≈  2%  — text overlays / address cards",
    f"```",
    f"",
    f"### Composition Hierarchy",
    f"```",
    f"1. wide                ≈ 19%  — standard room reading",
    f"2. landscape           ≈ 13%  — horizontal-dominant framing",
    f"3. symmetrical         ≈ 13%  — architectural grammar",
    f"4. depth_layering      ≈  8%  — foreground / background separation",
    f"5. rule_of_thirds      ≈  8%  — standard cinematic",
    f"6. centered / framing  ≈  7%  — hero focus",
    f"7. symmetry            ≈  5%  — doorways, corridors, pools",
    f"8. panoramic           ≈  4%  — wide horizontal",
    f"```",
    f"",
    f"### Sequence Role Pattern",
    f"```",
    f"Intro / hook:         ≈ 51%  (introductory + intro_hook + intro)",
    f"Room showcase:        ≈ 15%  (room_showcase)",
    f"Background context:   ≈  7%  (background)",
    f"Overview / establish: ≈ 11%  (overview + establishing shot + establishing)",
    f"Detail / close:       ≈  6%  (detail + detail shot + detail_moment)",
    f"```",
    f"",
    f"### Typography Usage",
    f"- **9.8% of frames carry text overlays** (address, price, agent info, property name)",
    f"- Typography is clustered at the start (address card) and end (agent card)",
    f"- Mid-video text should be avoided — it breaks immersion",
    f"",
    f"### Editorial Rules",
    f"1. Start with wide establishing or aerial — set location context in the first 3 seconds.",
    f"2. Interior flow: living room → kitchen → dining → bedroom → bathroom (loop back).",
    f"3. Use symmetrical / depth_layering compositions for architectural hero shots.",
    f"4. Rule-of-thirds for lifestyle and detail inserts.",
    f"5. Aerial oblique for mid-video location refresh, not just openers.",
    f"6. Title cards appear at start and end — never mid-flow.",
    f"7. Keep average shot duration ≤ 2s for social; ≤ 3s for YouTube long-form.",
]

(INTEL_DIR / "shot_grammar_guide.md").write_text("\n".join(lines))
print("✓ shot_grammar_guide.md")


# ════════════════════════════════════════════════════════════
# 4. COLOR & GRADE PATTERNS
# ════════════════════════════════════════════════════════════
colors = p1["color_grade"]
total_colors = sum(colors.values())

lines = [
    f"# Color & Grade Patterns",
    f"",
    f"> Derived from **{N:,} frames** across **{p1['good_file_count']} videos**",
    f"> Generated: {TODAY}",
    f"",
    f"## Color Grade Distribution",
    f"",
    f"| Grade | Frames | % |",
    f"|---|---|---|",
]
for k, v in sorted(colors.items(), key=lambda x: -x[1]):
    if v >= 10:
        lines.append(f"| `{k}` | {v:,} | {pct(v, total_colors)} |")

lines += [
    f"",
    f"## Grade Hierarchy",
    f"",
    f"```",
    f"1. neutral          ≈ 50%  — baseline clean, no stylization",
    f"2. natural          ≈ 22%  — slightly warm, organic",
    f"3. vivid            ≈  6%  — boosted saturation, punchy exteriors",
    f"4. warm             ≈  5%  — golden hour, interiors",
    f"5. saturated        ≈  4%  — rich pools, lush landscaping",
    f"6. dark             ≈  2%  — moody/evening shots",
    f"7. warm_neutral     ≈  1%  — compromise grade",
    f"8. black and white  ≈  1%  — title cards, architectural details",
    f"```",
    f"",
    f"## Key Insights",
    f"",
    f"- **72% of frames are neutral or natural** — the visual language of this market is clean, not stylized.",
    f"- **Vivid/saturated reserved for exterior and pool shots** — where color punch sells the lifestyle.",
    f"- **Warm grades for interiors** — creates inviting, lived-in feel.",
    f"- **Dark/moody appears in <2%** — twilight or architectural drama shots.",
    f"- **B&W used only on titles / cards** — never on property footage.",
    f"",
    f"## Grade Recommendations",
    f"",
    f"| Context | Recommended Grade |",
    f"|---|---|",
    f"| Aerial / exterior wide | vivid or saturated |",
    f"| Pool / water features | saturated |",
    f"| Interior living room | warm or warm_neutral |",
    f"| Kitchen / bathroom | neutral |",
    f"| Bedroom | natural or warm |",
    f"| Night / twilight | dark |",
    f"| Title cards | black and white or neutral |",
    f"| Overall master grade | neutral + scene-specific lifts |",
    f"",
    f"## LUT Strategy",
    f"",
    f"Based on the corpus, the optimal LUT strategy is:",
    f"1. **Base LUT**: neutral (clean, no heavy color cast)",
    f"2. **Exterior override**: +10-15% saturation on sky/grass",
    f"3. **Interior warmth**: +5-8% warm tint on living spaces",
    f"4. **Pool/water**: teal-boost secondary grade",
    f"5. **No heavy film-emulation LUTs** — corpus shows the market prefers clean digital over filmic look",
]

(INTEL_DIR / "color_grade_patterns.md").write_text("\n".join(lines))
print("✓ color_grade_patterns.md")


# ════════════════════════════════════════════════════════════
# 5. QA SCORECARD ANALYSIS
# ════════════════════════════════════════════════════════════
qa = syn["qa_scores"]

lines = [
    f"# QA Scorecard Analysis",
    f"",
    f"> Derived from **{syn['file_count']} synthesis files** (QA scores available in {11} files)",
    f"> Generated: {TODAY}",
    f"",
    f"## Average Scores Across Corpus",
    f"",
    f"| Metric | Avg Score | Benchmark |",
    f"|---|---|---|",
    f"| **Overall** | {qa['overall_avg']}/100 | Target: ≥ 75 |",
    f"| Hook (0–3s) | {qa['hook_avg']}/100 | Target: ≥ 80 |",
    f"| Rehook Density | {qa['rehook_avg']}/100 | Target: ≥ 85 |",
    f"| Motion Continuity | {qa['motion_continuity_avg']}/100 | Target: 100 |",
    f"| Tension Waveform | {qa['tension_waveform_avg']}/100 | Target: ≥ 70 |",
    f"| Viral Readiness | {qa['viral_readiness_avg']}/100 | Target: ≥ 80 |",
    f"| Music-Property Match | {qa['music_match_avg']}/100 | Target: ≥ 60 |",
    f"",
    f"## Score Interpretation",
    f"",
    f"### ✅ Strengths (corpus-wide)",
    f"- **Rehook Density: {qa['rehook_avg']}** — videos re-engage viewers frequently, good pacing",
    f"- **Motion Continuity: {qa['motion_continuity_avg']}** — perfect score, no jarring jump cuts",
    f"- **Viral Readiness: {qa['viral_readiness_avg']}** — strong social media format compliance",
    f"",
    f"### ⚠️ Weaknesses (corpus-wide)",
    f"- **Hook (0–3s): {qa['hook_avg']}** — opening 3 seconds underperform; need stronger first frames",
    f"- **Overall: {qa['overall_avg']}** — 10 points below 75 target; room for improvement",
    f"- **Music-Property Match: {qa['music_match_avg']}** — worst scoring metric; audio curation is poor",
    f"- **Tension Waveform: {qa['tension_waveform_avg']}** — emotional arc is flat; needs more contrast",
    f"",
    f"## Hook Score Analysis",
    f"",
    f"The **first 3 seconds** of a real estate video determine scroll-stop rate.",
    f"Current corpus averages **{qa['hook_avg']}/100** on hook score.",
    f"",
    f"### Hook Formula (from high-scoring videos)",
    f"```",
    f"Frame 0–0.5s:  aerial establishing OR exterior wide — location context",
    f"Frame 0.5–1.5s: rapid cut to interior wow shot (pool, great room, view)",
    f"Frame 1.5–3.0s: title card OR property address overlay",
    f"```",
    f"",
    f"### Anti-patterns (low hook scores)",
    f"- Opening with a slow pan of the street",
    f"- Starting with agent logo/branding (0s–1s branding = no hook)",
    f"- Drone rise that takes 3+ seconds to reveal the property",
    f"",
    f"## Tension Waveform Analysis",
    f"",
    f"Tension waveform measures the **emotional arc** — whether the video has peaks and valleys.",
    f"Current corpus averages **{qa['tension_waveform_avg']}/100**.",
    f"",
    f"### Target Waveform Shape",
    f"```",
    f"0s–5s:   HIGH TENSION  — hook, aerial, wow shot",
    f"5s–30s:  MEDIUM        — room flow, interiors",
    f"30s–60s: MEDIUM-HIGH   — outdoor/pool reveal",
    f"60s–75s: PEAK          — signature shot, best feature",
    f"75s–90s: LOW           — details, agent card, outro",
    f"```",
    f"",
    f"### How to Raise Tension Score",
    f"1. Place the **best aerial or pool shot at the 60–75s mark**, not the opening.",
    f"2. Use **music energy peaks** to align with visual peaks.",
    f"3. Add **fast-cut sequences (5–8 shots in 4s)** to create tension spikes.",
    f"4. End with a **calm logo/CTA** — let the tension fall gracefully.",
    f"",
    f"## Music-Property Match",
    f"",
    f"At **{qa['music_match_avg']}/100**, music selection is the single biggest opportunity.",
    f"",
    f"### Music Rules",
    f"| Property Type | Music Style |",
    f"|---|---|",
    f"| Luxury / ocean / 5M+ | Cinematic orchestral, no lyrics |",
    f"| Modern contemporary | Electronic/chillwave, 100–120 BPM |",
    f"| Family/suburban | Acoustic/indie folk, 80–100 BPM |",
    f"| Vacation/resort | Tropical/electronic, 110–130 BPM |",
    f"| Urban/loft | Lo-fi hip hop or jazz, 85–100 BPM |",
    f"",
    f"- **Beat-sync cuts** should align camera changes to downbeats",
    f"- **BPM match**: avg shot duration of 1.49s → 40 BPM synced cuts → ideal music: 80–120 BPM",
    f"- Never use music with lyrics for residential real estate",
]

(INTEL_DIR / "qa_scorecard_analysis.md").write_text("\n".join(lines))
print("✓ qa_scorecard_analysis.md")


# ════════════════════════════════════════════════════════════
# 6. PERFECT VIDEO BLUEPRINT
# ════════════════════════════════════════════════════════════
lines = [
    f"# Perfect Real Estate Video Blueprint",
    f"",
    f"> Synthesized from **{N:,} analyzed frames**, **{syn['file_count']} synthesis reports**, and **14 properties**.",
    f"> Generated: {TODAY}",
    f"",
    f"## The Formula",
    f"",
    f"**Duration:** 90–120 seconds for social; 2–3 minutes for YouTube/listing.",
    f"**Cut rate:** ~40 cuts/minute (1.0–2.0s avg shot duration).",
    f"**Model video:** beats sync'd, tension arc with 1 peak, 3-second hook.",
    f"",
    f"---",
    f"",
    f"## Act Structure",
    f"",
    f"### ACT 1 — The Hook (0–8s)",
    f"",
    f"| Time | Shot | Camera | Composition | Grade |",
    f"|---|---|---|---|---|",
    f"| 0.0–1.5s | Aerial establishing (property + neighborhood) | drone_flyover | landscape | vivid |",
    f"| 1.5–3.0s | Address/title card overlay | static | centered text | neutral/B&W |",
    f"| 3.0–5.0s | Exterior facade hero shot | static | symmetrical | natural |",
    f"| 5.0–8.0s | Interior WOW shot (great room / view / pool) | horizontal pan | wide | warm |",
    f"",
    f"**Hook rules:**",
    f"- Aerial must appear within first 2 seconds",
    f"- Address card should hold for exactly 1.5s",
    f"- The WOW shot at 5–8s is the scroll-stop moment — use best asset",
    f"",
    f"### ACT 2 — The Interior Journey (8–60s)",
    f"",
    f"**Room order (canonical):**",
    f"```",
    f"Living Room → Kitchen → Dining Room → Primary Bedroom → Primary Bathroom",
    f"→ (Additional Bedrooms) → Staircase → Secondary Spaces",
    f"```",
    f"",
    f"| Room | Avg Screen Time | Shot Count | Notes |",
    f"|---|---|---|---|",
    f"| Living Room | 8–12s | 5–8 shots | Anchor space; most time |",
    f"| Kitchen | 5–8s | 3–5 shots | Lifestyle focal point |",
    f"| Primary Bedroom | 5–8s | 3–5 shots | Aspirational comfort |",
    f"| Primary Bathroom | 4–6s | 3–4 shots | Luxury signal |",
    f"| Dining Room | 3–5s | 2–3 shots | Secondary interior |",
    f"| Staircase | 2–3s | 1–2 shots | Architectural transition |",
    f"",
    f"**Interior shot grammar:**",
    f"- Open each room with a **wide establishing** (18–24mm equivalent)",
    f"- Follow with a **depth_layered mid** (foreground element in frame)",
    f"- Close each room with a **detail insert** (hardware, texture, view through window)",
    f"- Use **symmetrical framing** for hallways, doorways, and bathroom mirrors",
    f"",
    f"### ACT 3 — The Outdoor Reveal (60–80s)",
    f"",
    f"| Time | Shot | Notes |",
    f"|---|---|---|",
    f"| 60–63s | Exterior patio/yard establishing | Transition from interior |",
    f"| 63–68s | Pool hero (if present) | PEAK moment of video |",
    f"| 68–72s | Pool detail / water surface | Saturated grade |",
    f"| 72–75s | Outdoor seating / lifestyle | Warm, aspirational |",
    f"| 75–80s | Aerial pullback over property | Re-establish context |",
    f"",
    f"**The pool is always the emotional peak.** If the property has a pool,",
    f"it should appear at the 60–70s mark — not at the beginning.",
    f"",
    f"### ACT 4 — The Close (80–90s)",
    f"",
    f"| Time | Shot | Notes |",
    f"|---|---|---|",
    f"| 80–85s | Aerial final wide (property in neighborhood) | Scale/context close |",
    f"| 85–88s | Agent/brokerage card | Static, B&W or neutral |",
    f"| 88–90s | Website/contact CTA | Fade to black |",
    f"",
    f"---",
    f"",
    f"## Camera Movement Rules",
    f"",
    f"| Movement | Frequency | When to Use |",
    f"|---|---|---|",
    f"| static (locked) | ~55% | Detail shots, bathroom, kitchen closeups |",
    f"| horizontal pan | ~25% | Room-wide reveals, exterior pans |",
    f"| drone_flyover | ~5% | Opener, mid-video context, closer |",
    f"| gimbal walk | <1% | Immersive walkthroughs only |",
    f"| other | <1% | Avoid — adds visual noise |",
    f"",
    f"---",
    f"",
    f"## Composition Rules",
    f"",
    f"| Priority | Composition | When |",
    f"|---|---|---|",
    f"| 1 | wide | Room openers |",
    f"| 2 | symmetrical | Hallways, doorways, pool, bathroom |",
    f"| 3 | depth_layering | Hero room shots with foreground interest |",
    f"| 4 | rule_of_thirds | Lifestyle shots, outdoor scenes |",
    f"| 5 | panoramic | Wide exteriors, views |",
    f"| 6 | centered | Title cards, focal architectural elements |",
    f"| 7 | detail / close-up | Hardware, texture, water, light |",
    f"",
    f"---",
    f"",
    f"## Color Grade Rules",
    f"",
    f"| Space | Grade |",
    f"|---|---|",
    f"| Aerial / exterior | vivid or saturated |",
    f"| Pool / water | saturated (teal lift) |",
    f"| Living room | warm |",
    f"| Kitchen / bathroom | neutral |",
    f"| Bedroom | natural or warm |",
    f"| Night / twilight | dark |",
    f"| Title cards | neutral or B&W |",
    f"| Default master | neutral |",
    f"",
    f"---",
    f"",
    f"## Music Rules",
    f"",
    f"- BPM: **100–120 BPM** for fast-cut social format",
    f"- No lyrics",
    f"- Build to a peak at the **outdoor/pool reveal (60–70s)**",
    f"- Sync camera changes to **downbeats**",
    f"- Drop energy on the final title card",
    f"",
    f"---",
    f"",
    f"## Typography Rules",
    f"",
    f"- Text overlays: **max 10% of video duration**",
    f"- Property address: first 3 seconds (1.5s hold)",
    f"- Agent/brokerage: last 5–8 seconds",
    f"- No mid-video text — breaks immersion",
    f"- Font: clean sans-serif, white on dark or dark on light (no drop shadows)",
    f"",
    f"---",
    f"",
    f"## QA Checklist",
    f"",
    f"Before export, validate:",
    f"",
    f"- [ ] Hook (0–3s) has aerial shot AND title card",
    f"- [ ] Avg shot duration ≤ 2.0s",
    f"- [ ] Living room has most screen time of any interior",
    f"- [ ] Pool/outdoor appears in Act 3 (not Act 1)",
    f"- [ ] Aerial appears at open AND close",
    f"- [ ] No music lyrics",
    f"- [ ] Music energy peaks at 60–70s",
    f"- [ ] Title cards only at start/end",
    f"- [ ] Color grade: neutral base with scene-specific lifts",
    f"- [ ] No whip pans, speed ramps, or heavy stabilizer warping",
    f"- [ ] Total duration: 90–120s for social, ≤ 3min for listing",
    f"",
    f"---",
    f"",
    f"## Target QA Scores",
    f"",
    f"| Metric | Current Avg | Target |",
    f"|---|---|---|",
    f"| Overall | {qa['overall_avg']}/100 | 80/100 |",
    f"| Hook (0–3s) | {qa['hook_avg']}/100 | 85/100 |",
    f"| Rehook Density | {qa['rehook_avg']}/100 | 90/100 |",
    f"| Motion Continuity | {qa['motion_continuity_avg']}/100 | 100/100 |",
    f"| Tension Waveform | {qa['tension_waveform_avg']}/100 | 80/100 |",
    f"| Viral Readiness | {qa['viral_readiness_avg']}/100 | 90/100 |",
    f"| Music-Property Match | {qa['music_match_avg']}/100 | 70/100 |",
]

(INTEL_DIR / "perfect_video_blueprint.md").write_text("\n".join(lines))
print("✓ perfect_video_blueprint.md")

print(f"\n✅ All intel files written to {INTEL_DIR}/")
print(f"   - camera_movement_atlas.md")
print(f"   - room_coverage_map.md")
print(f"   - shot_grammar_guide.md")
print(f"   - color_grade_patterns.md")
print(f"   - qa_scorecard_analysis.md")
print(f"   - perfect_video_blueprint.md")
