# Context — HyperEdit Orchestrator

Extended from: `skills/hyperedit-agent-master-orchestrator/CONTEXT.md`

## Source patterns from tutorials

- Simplicity and repeatability outperform complex edits.
- Song selection and structure are upstream decisions, not finishing tasks.
- Directional flow consistency is a core continuity rule.
- Workflow pass order reduces wasted work: story/build/refine → finishing passes.
- Hook alone is insufficient; periodic rehooks maintain watch time.

## Core planning heuristics

- Sequence by dependency, not by editor preference.
- Keep synthetic generation constrained to gaps with high narrative impact.
- Delay expensive processing (heavy denoise, color grading) until late stage.
- Preserve project type behavior:
  - **MLS**: clarity and room coverage first — all key rooms shown, hook = best wide exterior.
  - **Signature/viral**: tension cycles and creative peaks first — hook = most cinematic moment.
  - **Family friendly**: approachable pacing and warm tone — softer cuts, slower rhythm.

## Pipeline order rationale

1. **Footage first** — you cannot plan audio or assembly without knowing what clips exist.
2. **Audio before assembly** — music structure (BPM, phrases, radio edit) is the timeline skeleton. Assembly without a music map produces arbitrary cuts.
3. **Assembly before color** — grading on a cut that changes wastes compute and introduces inconsistency.
4. **Color before graphics** — captions and overlays must composite over the graded frame, not the ungraded one.
5. **Photo-to-video early (if needed)** — synthetic clips must be available before assembly starts.

## Failure patterns to watch

- Color done before edit lock → grading wasted on rework.
- Direction reversals across cuts → jarring, unprofessional.
- Excessive effects that distract from property value.
- Audio effects overpowering music.
- Caption styling that blocks subject faces or key property features.
- Assembling without the music map → cuts miss beats → pacing feels off.

## Decision matrix for conditional stages

### Photo-to-Video
- Run ONLY when `12_gap_report.has_blocking_gaps == true`.
- A gap is blocking if it prevents room coverage story from flowing.
- Prefer borrowing adjacent usable backup clips before generating synthetic footage.
- Reject synthetic inserts if visual realism QC fails.

### Text & Graphics
- Run ONLY when `00_project_brief.caption_required == true`.
- Not every video needs captions — many real estate videos are music-only.
- Short-form social (Reels, TikTok) almost always needs captions.
- MLS listings rarely need captions.

## Quality gate thresholds

| Gate | Pass | Warn | Fail |
|------|------|------|------|
| Hook timing | ≤ 5s | 5-8s | > 8s |
| Rehook interval | ≤ 8s | 8-12s | > 12s |
| Directional continuity | ≥ 0.8 | 0.6-0.8 | < 0.6 |
| Loudness (LUFS) | -14 ± 1 | -14 ± 2 | outside ± 3 |
| Caption safe area | all pass | none | any fail |
| Color-after-lock | true | — | false |

## Grading scale

| Grade | Meaning | Action |
|-------|---------|--------|
| A | All gates pass, publish ready | Deliver |
| B | Minor warnings, no blocking issues | Deliver with notes |
| C | Non-blocking issues, review needed | Flag to human reviewer |
| D | Blocking issues resolved but quality concerns | Retry affected stages |
| FAIL | Unresolved blocking issues | Do not deliver |

## Completion definition

Project is complete when:
- All stage artifacts are written and schema-valid.
- Every artifact has `status: "pass"` or accepted `status: "warn"` with `blocking_issues: []`.
- `72_publish_checklist.json` has `publish_ready: true`.
- Run-ledger `current_stage = "done"`.
