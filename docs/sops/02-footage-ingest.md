# SOP: Footage Ingest & Tagging

## Objective

Convert raw media into a ranked, sequence-ready shot pool with complete directional tags, shot class labels, room assignments, and gap analysis — ready for audio timing and assembly.

## Trigger

Dispatched by Orchestrator after `01_orchestration_plan.json` is written and `footage_intake` stage is `in_progress` in the run-ledger.

## Inputs

| Input | Source | Schema |
|-------|--------|--------|
| Project brief | `state/agents/<project_id>/00_project_brief.json` | `schemas/00_project_brief.schema.json` |
| Raw footage directory | `brief.footage_directory` | Filesystem path |
| Music style directive | `brief.music_style` | e.g. `uplifting modern 120-130 BPM` |
| Caption required flag | `brief.caption_required` | Boolean |
| Special instructions | `brief.special_instructions` | String |

## Prerequisites

- `00_project_brief.json` exists with `status: "pass"`.
- FFmpeg server running on `localhost:3333`.
- LM Studio vision model loaded (11B preferred, 8B fallback, 4B last resort — see `13-fallback-escalation.md`).
- `state/agents/<project_id>/` directory exists.

## Procedure

1. **Create FFmpeg session.**
   - `POST /session/create` → receive `session_id`.
   - Expected output: `session_id` stored in run context.

2. **Upload and ingest all raw clips.**
   - For each file in `footage_dir`: `POST /session/{id}/assets`.
   - Server auto-generates thumbnails and extracts metadata (duration, resolution, fps, codec).
   - Expected output: all clips uploaded, metadata available.

3. **Tag each clip with shot class.**
   - Use LM Studio vision model to classify: `wide_push` | `wide_orbit` | `detail_slider` | `drone_establishing` | `transition_shot` | `talking_head`.
   - Fallback ladder: 11B → 8B → 4B (see `13-fallback-escalation.md`).
   - Expected output: `shot_class` field on every clip.

4. **Tag room/zone and sequence block.**
   - Classify: `exterior` | `kitchen` | `living` | `bedroom` | `bathroom` | `amenities` | `drone`.
   - Expected output: `room_zone` and `sequence_block` fields on every clip.

5. **Tag directional movement.**
   - Classify: `left` | `right` | `forward` | `backward` | `straight_reset` | `orbit`.
   - Expected output: `direction` field on every clip.

6. **Score each clip (0.0–1.0).**
   - Technical quality: stability, exposure, focus.
   - Narrative value: hook potential, reveal quality, connector fit, payoff strength.
   - Continuity utility: movement match, room handoff compatibility.
   - Expected output: `scores.technical`, `scores.narrative`, `scores.continuity` on every clip.

7. **Build shortlist bins per sequence block.**
   - Select top-scoring clips per block, ensuring wide + detail coverage in each.
   - Apply format-specific heuristics from `CONTEXT.md`:
     - MLS: spatial orientation + room coverage first.
     - Reel/Signature: movement rhythm + emotional momentum.
   - Expected output: `11_selects_shortlist.json` with ranked bins.

8. **Detect coverage gaps.**
   - Required sequence plan: check each block for minimum wide + detail coverage.
   - Label each gap: `blocking` (story cannot continue without it) or `non_blocking`.
   - Apply fallback ladder for gaps before marking `blocking`:
     - Borrow from adjacent sequence block.
     - Reuse alternative take.
     - Speed-adjust existing clip if plausible.
     - Generate synthetic only if still blocked.
   - Expected output: `12_gap_report.json` with gap list + fallback recommendations.

9. **Optional: Upscale low-res clips.**
   - If any clip resolution < 1080p and `special_instructions` indicates upscaling: invoke video2x CLI.
   - `video2x -i clip.mp4 -o out.mp4 --scale-factor 2`
   - Expected output: upscaled clips replaced in session assets.

10. **Write outputs and validate.**
    - Write `10_footage_catalog.json`, `11_selects_shortlist.json`, `12_gap_report.json`.
    - Run schema validation: `scripts/validate-artifact.js`.
    - Expected output: all 3 artifacts with `status: "pass"` or `"warn"`.

## Quality Gates

| Gate | Pass | Warn | Fail |
|------|------|------|------|
| All clips tagged with shot class | 100% tagged | >90% tagged | <90% tagged |
| Direction tags on all shortlisted clips | 100% | — | Any missing |
| Each sequence block has ≥1 wide + ≥1 detail | All blocks covered | 1 block missing detail only | Any block missing wide |
| Hook candidate identified | ≥1 hook candidate | — | No hook candidate |
| Payoff candidate identified | ≥1 payoff candidate | — | No payoff candidate |
| Gaps labeled blocking/non_blocking | All labeled | — | Any unlabeled gap |

## Outputs

| Artifact | Path | Schema |
|----------|------|--------|
| Full tagged catalog | `state/agents/<project_id>/10_footage_catalog.json` | `schemas/10_footage_catalog.schema.json` |
| Ranked selects shortlist | `state/agents/<project_id>/11_selects_shortlist.json` | `schemas/11_selects_shortlist.schema.json` |
| Gap report with fallback plan | `state/agents/<project_id>/12_gap_report.json` | `schemas/12_gap_report.schema.json` |

## Failure Handling

- **Vision model unavailable**: Follow `13-fallback-escalation.md` — try 11B → 8B → 4B. If all fail, write tags as `unclassified` with `blocking_issues` entry.
- **FFmpeg server unreachable**: Return `BLOCKED: FFmpeg server not responding on :3333`. Check `npm run ffmpeg-server`.
- **Footage directory empty**: Return `BLOCKED: no media files found in footage_dir`.
- **<90% clips tagged**: Run a second vision pass on untagged clips before failing.
- **Retry policy**: Max 2 retries per clip for vision tagging. On persistent failure, mark clip `status: "warn"` and continue.
- **Escalation**: Write `blocking_issues` to artifact and surface to Orchestrator for human review.

## Downstream Dependencies

Completing this SOP unblocks:
- `03-photo-to-video.md` (if `12_gap_report.json` has `blocking` gaps with `source: "stills"`)
- `04-audio-radio-edit.md` (always — audio reads `11_selects_shortlist.json` for timing context)
- `05-assembly-picture-lock.md` (reads `11_selects_shortlist.json`)

## Skill Cross-Reference

- Skill: `skills/hyperedit-agent-footage-intake-sort/SKILL.md`
- Procedure matches: `skills/hyperedit-agent-footage-intake-sort/SOP.md` Steps 1–9
- Context: `skills/hyperedit-agent-footage-intake-sort/CONTEXT.md`
- Tool endpoints: `scripts/local-ffmpeg-server.js` — `/session/create`, `/session/{id}/assets`
