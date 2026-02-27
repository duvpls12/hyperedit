# SOP: Audio & Radio Edit

## Objective

Select music, analyze BPM and beat structure, and produce a radio edit timing plan that drives the entire assembly rhythm. Audio structure must be defined **before** assembly so cuts land on beats, not the other way around.

## Trigger

Dispatched by Orchestrator after `11_selects_shortlist.json` is written. Runs **before** assembly — the music map and radio edit are primary inputs to the assembler.

## Inputs

| Input | Source | Schema |
|-------|--------|--------|
| Footage selects shortlist | `state/agents/<project_id>/11_selects_shortlist.json` | `schemas/11_selects_shortlist.schema.json` |
| Project brief | `state/agents/<project_id>/00_project_brief.json` | `schemas/00_project_brief.schema.json` |
| Music style directive | `brief.music_style` | e.g. `uplifting modern 120-130 BPM` |
| Runtime target | `brief.target_duration_seconds` | Number (seconds) |

## Prerequisites

- `11_selects_shortlist.json` exists with `status: "pass"` or `"warn"`.
- FFmpeg server running on `localhost:3333`.
- Music library accessible.
- `state/agents/<project_id>/` directory exists.

## Procedure

1. **Select music track candidates.**
   - Read `brief.music_style` directive. If empty, infer from `delivery_format.aspect_ratio` and `special_instructions`.
   - Query music library for tracks matching the style and energy profile:
     - 9:16 social reel: energetic (120–140 BPM), strong drop and build structure.
     - 16:9 MLS/YouTube: moderate tempo (100–120 BPM), clean melodic, no lyrics.
     - Cinematic/signature: orchestral, spacious, architecturally resonant.
   - Select 2–3 candidates for final selection.
   - Expected output: candidate list with track metadata.

2. **Extract BPM and beat grid for each candidate.**
   - `POST /session/{id}/assets` — upload music track.
   - Invoke FFmpeg audio analysis: extract tempo, beat timestamps, bar markers.
   - Record: `bpm`, `beat_timestamps[]`, `bar_markers[]`, `total_duration_seconds`.
   - Expected output: beat grid data for each candidate.

3. **Identify structural markers per track.**
   - Mark: `intro_end`, `first_drop`, `build_peaks[]`, `chorus_hits[]`, `outro_start`.
   - These are the anchor points where cuts will align.
   - Expected output: `song_structure` map per candidate.

4. **Select final track.**
   - Choose track whose structure best matches the shot pool in `11_selects_shortlist.json`:
     - Count of sequence blocks ↔ number of song sections.
     - Runtime target ↔ song duration (prefer songs ≤ 10% longer than target).
   - Expected output: selected track recorded with selection rationale.

5. **Build radio edit timing plan.**
   - Map each sequence block to a song section:
     - Hook shots → intro/first hook of song.
     - Feature reveals → build sections.
     - Payoff/outro shots → song outro.
   - Define cut timing: assign each shortlisted clip a `cut_in_beat` and `cut_out_beat`.
   - Mark speed ramp positions: where beat drop or tempo change warrants a visual ramp.
   - Expected output: `31_radio_edit.json` with per-clip timing assignments.

6. **Validate radio edit timing.**
   - Sum of clip durations must match `runtime_target_seconds` ± 5%.
   - Every sequence block must be covered.
   - Hook must appear within first 3–5 seconds.
   - Rehook planned every 5–10 seconds.
   - Expected output: validation check results.

7. **Write outputs and validate schemas.**
   - Write `30_music_map.json` (BPM, beat anchors, song selection, structure map).
   - Write `31_radio_edit.json` (timing structure: per-clip beat assignments, speed ramp markers).
   - Write `32_audio_qc.json` (validation results: hook timing, rehook intervals, runtime match).
   - Run schema validation: `scripts/validate-artifact.js`.
   - Expected output: all 3 artifacts with `status: "pass"` or `"warn"`.

## Quality Gates

| Gate | Pass | Warn | Fail |
|------|------|------|------|
| BPM extracted for selected track | Present | — | Missing |
| Hook in first 3–5 seconds | ≤ 5s | 5–7s | > 7s |
| Rehook planned every 5–10s | All intervals covered | 1 interval > 10s | >1 interval > 10s |
| Runtime matches target ± 5% | Within 5% | 5–10% delta | > 10% delta |
| All sequence blocks assigned | 100% assigned | — | Any block unassigned |
| Beat grid complete | All beats mapped | Minor gaps | Major gaps / no beat data |

## Outputs

| Artifact | Path | Schema |
|----------|------|--------|
| Music map (BPM + structure) | `state/agents/<project_id>/30_music_map.json` | `schemas/30_music_map.schema.json` |
| Radio edit (timing structure) | `state/agents/<project_id>/31_radio_edit.json` | `schemas/31_radio_edit.schema.json` |
| Audio QC report | `state/agents/<project_id>/32_audio_qc.json` | `schemas/32_audio_qc.schema.json` |

## Failure Handling

- **No suitable music track found**: Return `BLOCKED: no matching track in library`. Surface to user — provide alternate library path or explicit track selection.
- **BPM extraction fails**: Retry with alternate FFmpeg analysis flags. On second failure, estimate BPM manually from structure markers. Document as `warn`.
- **Runtime mismatch > 10%**: Re-evaluate track selection or adjust timing plan. Max 2 retries before escalation.
- **Hook cannot land in first 5s**: Restructure sequence block assignments. If structurally impossible, document `warn` with justification.
- **Retry policy**: Max 2 retries for track selection + timing plan. On failure, surface to user with specific constraint list.
- **Escalation**: Orchestrator may override hook timing if client brief specifies alternate structure.

## Downstream Dependencies

Completing this SOP unblocks:
- `05-assembly-picture-lock.md` (Assembly reads `30_music_map.json` + `31_radio_edit.json` as primary inputs — cannot start without these)

## Skill Cross-Reference

- Skill: `skills/hyperedit-agent-audio-sound-design/SKILL.md`
- Procedure matches: `skills/hyperedit-agent-audio-sound-design/SOP.md` Steps 1–7
- Context: `skills/hyperedit-agent-audio-sound-design/CONTEXT.md`
- Tool endpoints: `scripts/local-ffmpeg-server.js` — `/session/{id}/assets`, audio analysis endpoints
- Note: This SOP covers music selection + radio edit (pre-assembly). Sound design (SFX/mix/ambience) is a downstream post-lock pass embedded in the final QC stage.
