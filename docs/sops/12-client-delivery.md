# SOP: Client Delivery & Handoff

## Objective

Export the final approved video in platform-appropriate formats, prepare the delivery package (video + metadata + publish checklist), and hand off to the client or upload to the target distribution platform.

## Trigger

Invoked by Orchestrator after `08-qa-grading.md` produces a grade of **A** or **B** (publish-ready).

## Inputs

| Input | Source | Schema |
|-------|--------|--------|
| Grade card | `state/agents/<project_id>/71_grade_card.json` | `schemas/71_grade_card.schema.json` |
| Publish checklist | `state/agents/<project_id>/72_publish_checklist.json` | `schemas/72_publish_checklist.schema.json` |
| Final video (captioned or graded) | `state/agents/<project_id>/captioned.mp4` or `graded.mp4` | — |
| Project brief | `state/agents/<project_id>/00_project_brief.json` | `schemas/00_project_brief.schema.json` |
| Target platform(s) | `brief.delivery_targets[]` | `instagram_reel` \| `youtube` \| `mls_embed` \| `download` |

## Prerequisites

- `71_grade_card.json` with `grade: "A"` or `"B"`.
- `72_publish_checklist.md` exists.
- Final video file exists at expected path.
- FFmpeg server running on `localhost:3333`.

## Procedure

1. **Select source video.**
   - If `62_graphics_qc.json` exists (captions applied): use `captioned.mp4`.
   - Otherwise: use `graded.mp4`.
   - Expected output: source video path confirmed.

2. **Export platform-specific formats.**
   - For each `delivery_target` in `brief.delivery_targets`:

   **Instagram Reel / TikTok:**
   - Format: MP4, H.264, 9:16, 1080×1920.
   - Audio: AAC 320kbps.
   - Max file size: 4GB (Reel), target ≤ 500MB.
   - `POST /session/{id}/render` with platform preset.

   **YouTube:**
   - Format: MP4, H.264, 16:9 or native AR.
   - Audio: AAC 384kbps.
   - Max resolution: source or 4K upscale.
   - `POST /session/{id}/render` with YouTube preset.

   **MLS Embed:**
   - Format: MP4, H.264, 16:9, 1080p.
   - Audio: AAC 192kbps.
   - Optimized for web streaming (fast start).

   **Download (Master):**
   - Format: MP4, H.264 or ProRes, full resolution.
   - Highest quality — no size optimization.

   - Expected output: per-platform export files in `state/agents/<project_id>/delivery/`.

3. **Apply platform-specific audio loudness normalization.**
   - Instagram/TikTok: -14 LUFS integrated.
   - YouTube: -14 LUFS integrated.
   - MLS Embed: -16 LUFS integrated.
   - Use FFmpeg loudnorm filter: `POST /session/{id}/process-asset`.
   - Expected output: loudness-normalized exports.

4. **Generate delivery metadata.**
   - Create `delivery_manifest.json`:
     - project_id, format_target, grade, export files list.
     - Per-file: filename, platform, resolution, file_size_mb, duration_seconds, loudness_lufs.
     - Delivery timestamp.
   - Expected output: `state/agents/<project_id>/delivery/delivery_manifest.json`.

5. **Final delivery review against publish checklist.**
   - Review `72_publish_checklist.json` — all `delivery_checklist_items` must be `true`:
     - Hook present in first 5s.
     - No color artifacts.
     - Audio loudness within platform target.
     - Captions legible (if applicable).
     - Grade A or B confirmed.
   - Expected output: checklist review complete.

6. **Package and hand off.**
   - Create delivery ZIP: all export files + `delivery_manifest.json` + `72_publish_checklist.md`.
   - Delivery path: `state/agents/<project_id>/delivery/<project_id>_delivery.zip`.
   - Surface delivery path to user.
   - Expected output: delivery ZIP ready for download or upload.

7. **Commit delivery to RAG.**
   - Invoke `10-rag-commit.md` for the delivery record.
   - Commit: grade, delivery targets, final platform specs, project metadata.
   - Expected output: delivery record in RAG index.

## Quality Gates

| Gate | Pass | Warn | Fail |
|------|------|------|------|
| Grade is A or B | A or B | — | C or D |
| All platform exports exist | All present | — | Any missing |
| File size within platform limit | All within limit | 1 slightly over | Any exceeds hard limit |
| Loudness within target ± 1 LUFS | Within range | ±1–2 LUFS | > ±2 LUFS |
| Publish checklist complete | All checked | — | Any unchecked |
| Delivery manifest written | Present | — | Missing |

## Outputs

| Artifact | Path |
|----------|------|
| Platform-specific exports | `state/agents/<project_id>/delivery/<platform>_<project_id>.mp4` |
| Delivery manifest | `state/agents/<project_id>/delivery/delivery_manifest.json` |
| Delivery ZIP | `state/agents/<project_id>/delivery/<project_id>_delivery.zip` |

## Failure Handling

- **Grade C or D**: Do not deliver. Return to `08-qa-grading.md` for rework path.
- **Export render fails**: Check FFmpeg server. Retry with fallback render settings. Common fix: reduce output bitrate.
- **File size exceeds platform limit**: Re-encode with lower bitrate. Document quality tradeoff as `warn`.
- **Loudness normalization fails**: Apply manually via FFmpeg loudnorm filter with explicit targets.
- **Retry policy**: Max 2 export retries per platform. On failure, surface specific error to user.
- **Escalation**: See `13-fallback-escalation.md`.

## Downstream Dependencies

- Final stage — no downstream pipeline dependencies.
- Output consumed by: client / PM dashboard / distribution platform.

## Skill Cross-Reference

- No dedicated skill file (manual/semi-automated for now — pending `skills/hyperedit-run-project/` integration).
- Tool endpoints: FFmpeg server `/session/{id}/render`, `/session/{id}/process-asset`
- Publish checklist: `state/agents/<project_id>/72_publish_checklist.md`
- Platform loudness targets: `-14 LUFS` (social), `-16 LUFS` (MLS)
