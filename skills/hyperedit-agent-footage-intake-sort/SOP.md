# SOP - Footage Intake and Sorting

## Objective

Convert raw media into a ranked, sequence ready shot pool with minimal assembly friction.

## Inputs

- `00_project_brief.json` — project format target (`mls`, `reel`, `highlight`, `ai_lot`), property profile, key selling points.
- Raw clips and metadata from footage directory.

## Procedure

1. Ingest all clips via FFmpeg server:
   - Create a session: `POST /session/create` → store `session_id`.
   - Upload each clip: `POST /session/{id}/assets` with the file — server auto-generates thumbnails and extracts metadata (duration, resolution, codec, fps).
   - If any clip is low-res (< 1080p) and upscaling is warranted, run video2x: `video2x -i clip.mp4 -o clip_upscaled.mp4 --scale-factor 2` before upload.
2. Extract a representative frame per clip for vision tagging:
   - Dispatch ComfyUI `VideoHelperSuite` workflow on local `:8188`: `Load Video (Upload)` → extract frame at mid-point → save as JPEG.
   - Submit each frame to LM Studio vision model with prompt: "Label this real estate video frame. Return JSON: shot_class (wide_push|wide_orbit|detail_slider|drone_establishing|transition_shot|talking_head), room_zone (exterior|kitchen|living|bed|bath|amenities|other), direction (left|right|forward|backward|straight_reset|orbit|static), stability (stable|shaky), exposure (good|under|over), focus (sharp|soft)."
3. Review and validate LM Studio tags per clip; correct any misclassified shot classes:
   - Valid `shot_class` values: `wide_push`, `wide_orbit`, `detail_slider`, `drone_establishing`, `transition_shot`, `talking_head`.
4. Confirm room/zone and sequence block assignment (exterior, kitchen, living, bed, bath, amenities).
5. Validate directional movement tags (`left`, `right`, `forward`, `backward`, `straight_reset`, `orbit`).
6. Score each clip:
   - Technical quality (stability, exposure, focus) — LM Studio provides initial scores; override if needed.
   - Narrative value (hook, reveal, connector, payoff).
   - Continuity utility (movement match, room handoff fit).
7. Create shortlist bins for each sequence block.
8. Detect gaps per required sequence plan.
9. Apply fallback ladder for gaps:
   - Borrow from adjacent sequence block.
   - Reuse alternative take.
   - Speed adjust existing clip if plausible.
   - Generate synthetic detail only if still blocked.
10. Write outputs and include assumptions/open questions.

## Quality gates

- No sequence block lacks both wide and detail options unless explicitly documented.
- Direction tags exist for all shortlisted clips.
- At least one viable hook candidate and one payoff candidate are identified.
- Gaps are labeled as `blocking` or `non_blocking`.

## Outputs

- `10_footage_catalog.json` full tagged inventory.
- `11_selects_shortlist.json` ranked per sequence.
- `12_gap_report.json` with fallback recommendations.
