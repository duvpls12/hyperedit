# SOP: Text, Graphics & Captions (Conditional)

## Objective

Add captions, title graphics, lower thirds, and tracked text overlays to the graded picture lock. All text must support the story without obstructing visuals, remain legible at mobile viewport size, and stay within safe areas.

## Trigger

Runs **only when** `brief.captions_required: true` OR `brief.graphics_required: true`. If both flags are false, skip this stage and proceed to `08-qa-grading.md`.

## Inputs

| Input | Source | Schema |
|-------|--------|--------|
| Picture lock | `state/agents/<project_id>/42_picture_lock.json` | `schemas/42_picture_lock.schema.json` |
| Graded video | `state/agents/<project_id>/graded.mp4` | — |
| Brand style | `brief.brand_style` | Colors, fonts, tone (clean/expressive) |
| Caption config | `brief.caption_config` | max_words_per_chunk, pause_threshold |
| Graphics spec | `brief.graphics_spec` | Price, location, feature callouts |

## Prerequisites

- `42_picture_lock.json` exists with `locked: true`.
- `52_color_qc.json` exists with `status: "pass"` or accepted `"warn"`.
- FFmpeg server running on `localhost:3333` (for Whisper transcription).
- Remotion available for caption rendering and motion graphics.
- Graded video file exists at expected path.

## Procedure

1. **Run Whisper transcription (if captions required).**
   - `POST /session/{id}/transcribe` → graded.mp4.
   - Returns word-level timing data.
   - Expected output: word timestamps array `[{word, start_ms, end_ms}]`.

2. **Build caption script with phrase-level chunking.**
   - Chunk words by: max 5 words per chunk OR ≥ 0.7s pause between words (whichever comes first).
   - Break by phrase and emphasis, not strict word count.
   - Write `60_caption_script.json` with chunked phrases + timing.
   - Expected output: caption script ready for layout.

3. **Select caption style by project type.**
   - MLS / family-friendly: clean and simple (white text, subtle drop shadow).
   - Signature reel: expressive but restrained (brand colors, minimal animation).
   - Apply consistent typography: font, weight, size, case, line spacing across all captions.
   - Expected output: style config recorded in `61_graphics_layout.json`.

4. **Timing pass: assign captions to timeline.**
   - Place each caption chunk at its start_ms position on the T1 caption track.
   - Each caption duration = end_ms of last word in chunk.
   - Expected output: captions placed on timeline with timing.

5. **Positioning pass: safe area compliance.**
   - Default position: lower-center safe zone (9:16 mobile viewport).
   - Per-shot adjustment: check if caption position blocks face, key property feature, or architectural element.
   - Move caption to upper zone if lower is obstructed.
   - Enforce safe area margins: 8% from all edges (mobile-first: platform UI overlays consume bottom zone).
   - Expected output: per-caption position assignments in `61_graphics_layout.json`.

6. **Add motion graphics and lower thirds (if required).**
   - Property price card: appear during establishing exterior shot, exit before cut.
   - Location lower third: appear during first interior sequence.
   - Feature callouts: appear when visual supports the claim immediately.
   - One key message at a time — no stacking.
   - Complex effects (zoom reveal, animated badge) reserved for hook or major reveal only.
   - Render via Remotion templates in `src/remotion/templates/`.
   - Expected output: graphics event list in `61_graphics_layout.json`.

7. **Add motion tracked text (if applicable).**
   - Only where motion tracking adds narrative value.
   - Validate depth and occlusion realism before approving.
   - Expected output: tracked text events with tracking metadata.

8. **Render caption layer via Remotion.**
   - `POST /session/{id}/render-motion-graphic` with caption data → rendered caption overlay.
   - Composite over graded video using FFmpeg: `POST /session/{id}/process-asset`.
   - Expected output: captioned video file.

9. **Run mobile viewport QC.**
   - Verify all captions within safe margins (8% from all edges).
   - Typography legible at 375px width (iPhone SE).
   - No caption collides with face, key property feature, or architectural element.
   - Motion graphics are subtle and purpose-driven.
   - Expected output: `62_graphics_qc.json` with per-check pass/warn/fail.

10. **Write outputs and validate.**
    - Write `60_caption_script.json`, `61_graphics_layout.json`, `62_graphics_qc.json`.
    - Run schema validation: `scripts/validate-artifact.js`.
    - Expected output: all 3 artifacts with `status: "pass"` or `"warn"`.

## Quality Gates

| Gate | Pass | Warn | Fail |
|------|------|------|------|
| No caption collision with face or key feature | 0 collisions | — | Any collision |
| Safe area margins respected | 100% within margins | — | Any outside margins |
| Typography consistent across all captions | Consistent | Minor variation | Inconsistent font/weight |
| Caption legible at 375px width | All legible | — | Any illegible |
| Max 5 words per caption chunk | All ≤ 5 words | — | Any > 5 words |
| Motion graphics subtle and purposeful | All purposeful | 1 decorative | >1 decorative |
| No stacked text elements | 0 overlapping | — | Any overlap |
| Tracked text locked to scene motion | 0 drift | Minor drift | Visible drift |

## Outputs

| Artifact | Path | Schema |
|----------|------|--------|
| Caption script | `state/agents/<project_id>/60_caption_script.json` | `schemas/60_caption_script.schema.json` |
| Graphics layout | `state/agents/<project_id>/61_graphics_layout.json` | `schemas/61_graphics_layout.schema.json` |
| Graphics QC report | `state/agents/<project_id>/62_graphics_qc.json` | `schemas/62_graphics_qc.schema.json` |
| Captioned video | `state/agents/<project_id>/captioned.mp4` | — |

## Failure Handling

- **Whisper transcription fails (local)**: Fallback to Gemini API transcription. Document as `warn` — Gemini may struggle with long audio. See `13-fallback-escalation.md`.
- **Caption collision with face**: Move to upper zone or reduce size. If still colliding, document `warn` with timestamp.
- **Remotion render error**: Check Remotion version compatibility. Fallback to FFmpeg text overlay for simple captions.
- **Motion tracking fails**: Remove tracked text, use static position. Document as `warn`.
- **Retry policy**: Max 2 passes for caption positioning. On persistent collision, document `warn` and proceed.
- **Escalation**: Orchestrator may downgrade to captions-only (skip motion graphics) under time constraint.

## Downstream Dependencies

Completing this SOP unblocks:
- `08-qa-grading.md` (Orchestrator final QC — reads captioned video or graded video if captions skipped)

## Skill Cross-Reference

- Skill: `skills/hyperedit-agent-graphics-captions/SKILL.md`
- Procedure matches: `skills/hyperedit-agent-graphics-captions/SOP.md` Steps 1–9
- Context: `skills/hyperedit-agent-graphics-captions/CONTEXT.md`
- Tool endpoints: FFmpeg server `/session/{id}/transcribe`, `/session/{id}/render-motion-graphic`
- Remotion templates: `src/remotion/templates/` + `src/remotion/DynamicAnimation.tsx`
- Caption chunking config: `max_words: 5`, `pause_threshold: 0.7s` (matches CLAUDE.md spec)
