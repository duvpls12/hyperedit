# SOP: Assembly & Picture Lock

## Objective

Build the complete video timeline from the music map and shot pool, progressing from rough cut through refine pass to a frozen picture lock. Cuts must land on beats. No color, graphics, or audio finishing happens before this stage is complete.

## Trigger

Dispatched by Orchestrator after both `31_radio_edit.json` (audio timing) and `11_selects_shortlist.json` (shot pool) are written with `status: "pass"` or accepted `"warn"`.

## Inputs

| Input | Source | Schema |
|-------|--------|--------|
| Footage selects shortlist | `state/agents/<project_id>/11_selects_shortlist.json` | `schemas/11_selects_shortlist.schema.json` |
| Music map | `state/agents/<project_id>/30_music_map.json` | `schemas/30_music_map.schema.json` |
| Radio edit timing plan | `state/agents/<project_id>/31_radio_edit.json` | `schemas/31_radio_edit.schema.json` |
| Approved synthetic clips (optional) | `state/agents/<project_id>/21_generated_clips.json` | `schemas/21_generated_clips.schema.json` |
| Project brief | `state/agents/<project_id>/00_project_brief.json` | `schemas/00_project_brief.schema.json` |

## Prerequisites

- `30_music_map.json` and `31_radio_edit.json` exist with `status: "pass"` or `"warn"`.
- `11_selects_shortlist.json` exists with `status: "pass"` or `"warn"`.
- `<project>/proxies/` directory contains 720p proxy files for all shortlisted clips.
- FFmpeg server running on `localhost:3333`.
- ComfyUI + VideoHelperSuite available for final export (Video Combine).
- `state/agents/<project_id>/` directory exists.

## Proxy-First Editing Rule

**All timeline operations in this SOP use 720p proxy files, NOT raw footage.** This keeps assembly fast and avoids processing 4K/HEVC during creative editing. Each clip in `11_selects_shortlist.json` includes a `proxy_path` field pointing to `<project>/proxies/<clip_id>_proxy.mp4`. The `42_picture_lock.json` must include a `source_path` → `proxy_path` mapping for every clip so the Color agent can conform (replace proxies with full-res graded files).

## Procedure

1. **Load timing map and shot pool.**
   - Parse `31_radio_edit.json` — extract per-clip beat assignments and speed ramp markers.
   - Parse `11_selects_shortlist.json` — load shortlisted clips with directional tags.
   - Merge optional `21_generated_clips.json` into the pool.
   - Expected output: merged shot pool with timing anchors.

2. **Rough cut — build sequence by block (radio pass).**
   - For each sequence block in order: hook, tease, reveal, room progression, payoff/outro.
   - Place clips at assigned beat markers from `31_radio_edit.json`.
   - Enforce directional flow: keep consistent lateral direction through mini-sequences; use `straight_reset` clips before switching direction.
   - Expected output: `40_rough_cut.json` with clip list, in/out points, beat-aligned cut points.

3. **Insert speed ramps at marked positions.**
   - Place speed ramps at positions flagged in `30_music_map.json → speed_ramp_markers`.
   - Confirm each ramp has sufficient pre/post motion footage (≥ 1s each side).
   - Pre-stabilize clips before speed ramping.
   - Expected output: speed ramp entries in `40_rough_cut.json`.

4. **Validate rough cut directional continuity.**
   - Check every adjacent cut pair: no left-right whiplash (direction reversal without reset).
   - Score: continuity score ≥ 0.8 required.
   - Expected output: continuity score in rough cut QC fields.

5. **Refine pass.**
   - Remove redundant clips (same shot class + direction in consecutive cuts).
   - Trim dead air (clips with > 0.5s static before movement starts).
   - Confirm wide/detail alternation throughout — no run of > 2 same shot class.
   - Verify runtime within target ± 5%.
   - Ask: would a viewer rewatch? If not, identify the weak point and replace.
   - Expected output: `41_refine_cut.json` with refined clip list.

6. **Final picture lock check.**
   - All quality gates must pass (see below).
   - No further visual edits allowed after this point — color and graphics will be applied to this exact cut.
   - Expected output: `42_picture_lock.json` with `status: "pass"` and `locked: true`.

7. **Export picture lock via VideoHelperSuite.**
   - Invoke ComfyUI workflow `skills/comfyui-workflows/video-combine.json`: combine frames + music → export locked video.
   - Export path: `state/agents/<project_id>/picture_lock.<ext>`.
   - Expected output: picture lock video file written.

8. **Write outputs and validate.**
   - Write `40_rough_cut.json`, `41_refine_cut.json`, `42_picture_lock.json`.
   - Run schema validation: `scripts/validate-artifact.js`.
   - Expected output: all 3 artifacts with `status: "pass"`.

## Quality Gates

| Gate | Pass | Warn | Fail |
|------|------|------|------|
| Hook in first 3–5 seconds | ≤ 5s | 5–7s | > 7s |
| Rehook every 5–10s (social formats) | All intervals | 1 interval 10–12s | Any > 12s or missing |
| Directional continuity score | ≥ 0.8 | 0.7–0.79 | < 0.7 |
| No left-right whiplash | 0 violations | — | Any violation |
| Wide/detail alternation present | No run > 2 same class | Run of 3 | Run of ≥ 4 |
| Speed ramps have sufficient footage | All ramps ≥ 1s each side | — | Any ramp < 0.5s |
| Cuts aligned to beat markers | ≥ 90% within 1 beat | 80–89% | < 80% |
| Runtime within target ± 5% | ≤ 5% delta | 5–10% delta | > 10% delta |
| Picture lock frozen | `locked: true` | — | Not marked locked |

## Outputs

| Artifact | Path | Schema |
|----------|------|--------|
| Rough cut plan | `state/agents/<project_id>/40_rough_cut.json` | `schemas/40_rough_cut.schema.json` |
| Refined cut plan | `state/agents/<project_id>/41_refine_cut.json` | `schemas/41_refine_cut.schema.json` |
| Picture lock (frozen) | `state/agents/<project_id>/42_picture_lock.json` | `schemas/42_picture_lock.schema.json` |
| Picture lock video | `state/agents/<project_id>/picture_lock.mp4` | — |

## Failure Handling

- **Directional continuity < 0.7**: Identify whiplash pairs, swap adjacent clips or insert `straight_reset`. Max 2 refine passes before escalation.
- **Runtime > 10% off target**: Re-evaluate sequence block durations. Remove lowest-narrative-value clips first. Do not cut hooks or payoffs.
- **Speed ramp has insufficient footage**: Use alternate clip from same sequence block. If none available, remove speed ramp and document `warn`.
- **VideoHelperSuite export fails**: Fallback to FFmpeg server `POST /session/{id}/render` for export.
- **Retry policy**: Max 2 retries for rough cut + refine pass. On failure, surface specific blocker list to Orchestrator.
- **Escalation**: Orchestrator may override one quality gate with `accepted_warn` to unblock color stage.

## Downstream Dependencies

Completing this SOP (picture lock frozen) unblocks:
- `06-color-grading.md` (Color runs ONLY after picture lock — no wasted grading on cuts that change)
- `07-text-graphics-captions.md` (if applicable — reads picture lock for caption timing)

## Skill Cross-Reference

- Skill: `skills/hyperedit-agent-assembly-editor/SKILL.md`
- Procedure matches: `skills/hyperedit-agent-assembly-editor/SOP.md` Steps 1–8
- Context: `skills/hyperedit-agent-assembly-editor/CONTEXT.md`
- Tool endpoints: FFmpeg server `/session/{id}/render`, ComfyUI VideoHelperSuite (Video Combine)
- ComfyUI workflow: `skills/comfyui-workflows/video-combine.json`
