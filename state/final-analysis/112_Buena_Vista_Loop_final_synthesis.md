# Final Synthesis — 112 Buena Vista Loop

## Core Metrics
- Frames analyzed: **477** @ 5 fps
- Shot count (temporal pass): **102**
- Movement mix: **static=7, pan=95**
- Typography presence: **102/477 frames** (21.4%)
- Audio BPM: **103.359375**

## Visual Narrative Summary
The cut opens with a prolonged title-card/fireplace phase, then transitions into interior/exterior listing coverage with frequent short shot boundaries. The cadence is aggressive (102 shots over ~95s sampled timeline), favoring quick segmentation over long architectural holds.

## Room/Amenity Coverage (frame-level frequency)
unknown (111), living room (104), fireplace (59), bedroom (45), bathroom (26), dining room (23), kitchen (22), none (19)

## Sequence Role Distribution
establishing shot (336), intro (50), establishing (36), title card (33), opening title (6), intro/logo (5), intro/title card (4), intro / title card (3)

## Camera Motion Observations
pan (95), static (7)

## Audio + Music Fit
- DSP baseline completed (tempo/onset/energy/brightness).
- Qwen2-audio semantic pass completed.
- Gemma recommender summary: **Fast tempo with moderate energy. Features prominent bass and hi-hat patterns.**
- Suggested tracks/styles: Electro House - Dubstep Remix, Acid House - Acid House Reimagined

## QA Flags
1. **Shot fragmentation is high** (102 shots / 477 sampled frames) — likely over-sensitive cut detection.
2. **Audio recommendations are generic/off-domain** (electro/acid suggestions not aligned to luxury RE by default).
3. **Final report quality gate failed previously** due to shallow template output. This file replaces that minimal output.

## Editor Actions
- Re-run temporal boundary thresholds with min-shot-duration floor to reduce micro-cuts.
- Add domain prior for music recommendations (cinematic/lounge/organic house/piano-led options by property mood).
- Keep title-card duration under control at opening unless branding-first is intentional.
