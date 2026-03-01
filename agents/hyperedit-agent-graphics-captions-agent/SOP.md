# SOP - On Screen Graphics and Captions

## Objective

Increase comprehension and retention using captions and graphics that support the story without obstructing visuals.

## Inputs

- `42_picture_lock.json` — clip list with paths and timing from assembly.
- Dialogue audio (extracted from picture lock video or A1/A2 tracks).
- Brand style constraints (from `00_project_brief.json`).

## Procedure

1. Transcribe dialogue audio via FFmpeg server Whisper:
   - `POST /session/{id}/transcribe` with audio file → returns word-level timestamps array.
   - Chunk transcript: split at max 5 words OR when inter-word pause >= 0.7s (whichever comes first).
   - Write word timestamps and chunks to `60_caption_script.json`.
2. Select caption style by project type:
   - Family-friendly MLS: clean sans-serif, white text, subtle dark background pill.
   - Signature reel: expressive but restrained — slightly larger, minimal animation.
3. Apply captions timing pass first: map each chunk start/end to timeline positions from `42_picture_lock.json`.
4. Layout pass: position each caption chunk in center-bottom safe zone (9:16: 8% padding all sides).
   - Keep key subject areas visible; position text to retain face and feature visibility.
   - Adapt placement per shot (move caption if subject fills bottom zone).
5. Add motion tracked text only where it adds narrative value (e.g., property address reveal, price callout at hook).
6. For supporting graphics (price, location, feature callouts):
   - Use Remotion template via FFmpeg server: `POST /session/{id}/render-motion-graphic` with template name and data props.
   - Apply consistent visual hierarchy — one key message at a time.
7. For 3D tracked titles (optional, signature reels only): validate depth and occlusion realism before committing.
8. Composite captions and graphics via FFmpeg server: `POST /session/{id}/process-asset` with overlay filter chain.
9. Run mobile viewport QC: verify safe margins at 9:16, readability at 390px phone width, no collisions with faces or property features.

## Quality gates

- No caption collisions with faces or key property details.
- Typography remains consistent and legible at phone viewing size.
- Motion graphics are subtle and purpose driven.
- Any tracked text remains locked to scene motion.

## Outputs

- `60_caption_script.json` — chunked transcript with word timestamps, chunk boundaries, style selection.
- `61_graphics_layout.json` — per-element layout: position, timing, template name, data props, track assignment.
- `62_graphics_qc.json` — pass/warn/fail: safe-area compliance, collision checks, typography consistency, animation subtlety.
