# SOP - Assembly Editor

## Objective

Build a compelling narrative timeline by placing approved shots on beat anchors from the music map. Produce rough cut → refine cut → picture lock. Cuts land on beats — never placed by visual feel alone.

## Inputs

- `11_selects_shortlist.json` — approved clips with shot class, room, direction, score, file paths
- `30_music_map.json` — BPM, `beat_timestamps[]`, `structural_anchors{}`, total track duration
- `31_radio_edit.json` — `edit_in_seconds`, `edit_out_seconds`, `beat_anchors_used[]`, `radio_edit_duration`
- `21_generated_clips.json` (optional) — synthetic inserts from photo-to-video agent

## Procedure

### Phase 1: Load beat grid

1. Read `30_music_map.json` — extract `beat_timestamps[]` and `structural_anchors{}` (intro, verse, chorus, drop, outro).
2. Read `31_radio_edit.json` — extract the usable beat window: `edit_in_seconds` → `edit_out_seconds`, all `beat_anchors_used[]`.
3. Build a working cut grid: list of beat positions within the radio edit window that are available as cut points.

### Phase 2: Sequence planning (narrative arc)

4. Read `11_selects_shortlist.json` — group shots by: hook candidates (high energy, wide, striking), detail reveals, room progressions, payoff/outro candidates.
5. Map narrative arc to structural anchors:
   - `intro_start` → hook shot (first 3–5s, highest-impact clip)
   - `verse_start` → tease details / room by room
   - `chorus_start` / `drop_start` → major reveal (best wide or hero shot)
   - `outro_start` → payoff and close
6. If `21_generated_clips.json` exists, insert synthetic clips at identified gap positions (flagged in `12_gap_report.json`).

### Phase 3: Rough cut

7. Place shots sequentially, each starting on a beat timestamp from the cut grid.
8. Enforce directional flow: keep consistent lateral direction within mini-sequences; use straight push clips as neutral reset before reversing direction.
9. Alternate wide and detail shots for rhythm and spatial clarity.
10. Mark speed ramp positions: insert speed ramp where transition energy is needed; ensure ≥0.5s of pre/post motion around each ramp anchor.
11. Write `40_rough_cut.json`: `{ clips: [{ asset_id, start_beat, end_beat, in_point, out_point, speed_ramp?, shot_class }], total_duration, beat_alignment_score, assumptions[], open_questions[] }`

### Phase 4: Refine pass

12. Remove redundancy — flag clips with same shot class in consecutive positions unless intentional rhythm repeat.
13. Trim dead air — clips with < 0.3s visible motion at cut points.
14. Confirm wide/detail alternation maintains visual rhythm.
15. Verify hook is in first 3–5s and at least one rehook every 5–10s.
16. Check runtime against `radio_edit_duration` — difference must be ≤ 2s.
17. Write `41_refine_cut.json`: updated clip list + `refinements_made[]` + `qc_flags[]`.

### Phase 5: Picture lock

18. Final check: no avoidable left-right whiplash between adjacent cuts.
19. Confirm speed ramps hit beat landmarks (within 50ms tolerance).
20. Render timeline via FFmpeg server: `POST /session/{id}/render` with clip sequence JSON.
21. Export final cut via VideoHelperSuite Video Combine (frames + audio → output file).
22. Write `42_picture_lock.json`: `{ status, output_file_path, total_duration, beat_alignment_score, clips[], blocking_issues[], assumptions[], open_questions[] }`

## Quality gates

- Hook in first 3–5 seconds — FAIL if missing
- At least one rehook every 5–10s — WARN if skipped for > 10s
- No avoidable left-right whiplash between adjacent cuts — WARN per violation
- Speed ramps hit beat landmarks (within 50ms) — FAIL if ramp anchor misses beat by > 100ms
- Runtime within ±2s of `radio_edit_duration` — PASS; ±2–5s — WARN; > ±5s — FAIL
- Beat alignment score ≥ 0.85 (ratio of cuts landing on beats) — PASS; 0.7–0.84 — WARN; < 0.7 — FAIL

## Outputs

- `40_rough_cut.json` — initial clip sequence with beat alignment
- `41_refine_cut.json` — refined clip sequence with redundancy removed and QC flags
- `42_picture_lock.json` — final locked cut with rendered output path and full QC status
