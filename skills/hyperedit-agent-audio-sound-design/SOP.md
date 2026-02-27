# SOP - Audio Agent (Music Selection, BPM Analysis, Radio Edit)

## Objective

Select music, analyze BPM and beat grid via FFmpeg server, and produce a radio edit structure that the Assembly agent uses to align all timeline cuts to beats.

## Inputs

- `00_project_brief.json` — tone, energy target, platform, target duration
- `11_selects_shortlist.json` — approved clips with durations (used to calculate total cut pool runtime)
- Music library directory (path from project brief or config)

## Procedure

1. **Read project brief** — extract tone (e.g., luxury, upbeat, cinematic), platform (Instagram Reel, YouTube, MLS), and target video duration.
2. **Calculate target duration from selects** — sum clip durations in `11_selects_shortlist.json`; use as reference for music segment length.
3. **Select music track** — from library, match track energy and mood to brief tone targets. Prefer tracks with clear intro/drop/outro structure. Record: `track_path`, `track_title`, `bpm_estimate` (if labeled), `duration_seconds`.
4. **Extract audio via FFmpeg server**:
   - `POST /session/{id}/extract-audio` with track path
   - Returns: separated audio asset ID
5. **Detect BPM and build beat grid**:
   - `POST /session/{id}/process-asset` with `silencedetect` + aubio/essentia filter chain or FFmpeg beat detection
   - Parse output to extract: `bpm`, `beat_timestamps[]` (array of seconds from 0.0 to track end)
   - If BPM detection confidence < 0.8, attempt alternate method or flag `warn` in QC
6. **Map structural anchors** — listen/analyze for structural sections and mark their beat positions:
   - `intro_start`, `verse_start`, `chorus_start`, `drop_start`, `bridge_start`, `outro_start`
   - Each anchor maps to nearest strong beat timestamp
7. **Construct radio edit** — define the segment of the track that fits target duration:
   - Identify edit in/out points landing on strong beats (preferably bar boundaries)
   - If target duration requires a cut within the track, mark crossfade point at a beat boundary
   - Validate: `radio_edit_duration` within ±5s of target video duration
8. **Write artifacts**:
   - `30_music_map.json`: `{ track_path, bpm, beat_timestamps[], structural_anchors{}, total_track_duration }`
   - `31_radio_edit.json`: `{ edit_in_seconds, edit_out_seconds, radio_edit_duration, crossfade_points[], beat_anchors_used[], assumptions[], open_questions[] }`
   - `32_audio_qc.json`: QC result (see Quality Gates)

## Quality gates

- `bpm_confidence >= 0.8` — PASS; 0.6–0.79 — WARN; < 0.6 — FAIL
- Beat grid covers 100% of radio edit duration — PASS; gaps > 5s — WARN
- `radio_edit_duration` within ±5s of target — PASS; ±6–10s — WARN; > ±10s — FAIL
- Edit in/out points land on beat boundaries (within 50ms) — PASS
- No QC issues — PASS; any WARN → proceed with flag; any FAIL → block assembly

## Outputs

- `30_music_map.json` — BPM, beat timestamps, structural anchors, selected track metadata
- `31_radio_edit.json` — Radio edit timing structure mapped to beat anchors
- `32_audio_qc.json` — QC result with `status` (pass/warn/fail), `blocking_issues`, `assumptions`, `open_questions`
