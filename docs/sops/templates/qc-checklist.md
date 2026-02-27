# QC Checklist — Universal Quality Gate

> Complete this checklist before marking any stage `done`. All `FAIL` items must be resolved or escalated before advancing.

**Project ID:** `<project_id>`
**Stage:** `<stage_name>`
**Checked by:** `<agent_skill_name>`
**Date:** `<YYYY-MM-DD>`

---

## Stage 1: Project Kickoff

- [ ] Client brief parsed and schema-valid
- [ ] All required fields present (`project_id`, `format_target`, `footage_dir`, `runtime_target_seconds`)
- [ ] `format_target` is a valid enum value
- [ ] `footage_dir` exists and is readable
- [ ] Run-ledger initialized with all 7 stages as `pending`
- [ ] Orchestration plan written with per-stage gate definitions

---

## Stage 2: Footage Intake

- [ ] All clips ingested (session_id recorded)
- [ ] Shot class tagged on ≥ 90% of clips
- [ ] Room/zone tagged on all shortlisted clips
- [ ] Directional movement tagged on all shortlisted clips
- [ ] Each sequence block has ≥ 1 wide + ≥ 1 detail clip
- [ ] At least 1 hook candidate identified
- [ ] At least 1 payoff candidate identified
- [ ] All gaps labeled `blocking` or `non_blocking`
- [ ] Schema validation passed for all 3 artifacts

---

## Stage 3: Photo-to-Video (if run)

- [ ] Only blocking gaps targeted for generation
- [ ] Source stills color-normalized before export
- [ ] 2–3 variants generated per request
- [ ] No visible warping, flicker, or impossible camera motion in approved clips
- [ ] Geometry consistent (no morphing walls/floors)
- [ ] Synthetic usage ≤ 20% of total timeline duration
- [ ] Provenance metadata present (tool, prompt, seed, model) on all generated clips
- [ ] Rejection reasons recorded for failed variants

---

## Stage 4: Audio & Radio Edit

- [ ] BPM extracted for selected track
- [ ] Beat timestamps and bar markers recorded
- [ ] All structural markers identified (intro, drop, build, outro)
- [ ] Hook cut planned within first 3–5 seconds
- [ ] Rehook planned every 5–10 seconds for social formats
- [ ] All sequence blocks assigned to song sections
- [ ] Runtime plan within ±5% of `runtime_target_seconds`
- [ ] `30_music_map.json` and `31_radio_edit.json` schema-valid

---

## Stage 5: Assembly & Picture Lock

- [ ] Music map and radio edit loaded as timing basis
- [ ] All cuts aligned to beat markers (≥ 90% within 1 beat)
- [ ] Hook in first 3–5 seconds ✓
- [ ] Rehook every 5–10 seconds ✓ (social formats)
- [ ] Directional continuity score ≥ 0.8
- [ ] No left-right whiplash without `straight_reset`
- [ ] Wide/detail alternation — no run of > 2 same shot class
- [ ] Each speed ramp has ≥ 1s footage on each side
- [ ] Runtime within ±5% of target
- [ ] Picture lock marked `locked: true`
- [ ] Picture lock video exported

---

## Stage 6: Color Grading

- [ ] Color applied AFTER picture lock (`created_at > locked_at` verified)
- [ ] Log footage has conversion LUT applied (if applicable)
- [ ] No clipped highlights (waveform checked)
- [ ] No crushed blacks (waveform checked)
- [ ] White balance consistent across adjacent cuts
- [ ] Creative LUT applied at 30–60% intensity
- [ ] Cross-clip consistency ΔE < 5 (average)
- [ ] Special cases documented (windows, drone, skin tones)
- [ ] Graded video exported

---

## Stage 7: Text, Graphics & Captions (if run)

- [ ] Whisper transcription completed (or Gemini fallback documented)
- [ ] Caption chunks ≤ 5 words each
- [ ] Caption timing derived from word timestamps
- [ ] All captions within 8% safe area margins (mobile-first)
- [ ] No caption collision with face or key property feature
- [ ] Typography consistent across all captions (font/weight/size/case)
- [ ] Captions legible at 375px viewport width
- [ ] Motion graphics are subtle and purpose-driven
- [ ] No stacked text elements
- [ ] Captioned video exported

---

## Stage 8: QA & Grading

- [ ] All required artifacts present in `state/agents/<project_id>/`
- [ ] Hook timing verified (≤ 5s)
- [ ] Rehook timing verified (all 5–10s intervals covered)
- [ ] Directional continuity ≥ 0.8 confirmed
- [ ] Color-after-lock timestamp sequence confirmed
- [ ] Caption safe area confirmed (if applicable)
- [ ] Beat-aligned cuts ≥ 90%
- [ ] All speed ramps have matching audio accents
- [ ] No unresolved blocking issues
- [ ] Grade assigned: A / B / C / D
- [ ] Grade card written with dimension scores and deficiency callouts (0–10 per dimension)
- [ ] `72_publish_checklist.json` written with `delivery_checklist_items` populated

---

## Final Delivery (if Grade A or B)

- [ ] Grade is A or B (not C or D)
- [ ] Platform exports generated for all `delivery_targets`
- [ ] All exports within platform file size limits
- [ ] Loudness normalized to platform target (−14 LUFS social, −16 LUFS MLS)
- [ ] Delivery manifest written
- [ ] Delivery ZIP packaged
- [ ] RAG commit completed for full project record

---

## Critical Rules (apply to every stage)

- [ ] No downstream stage overwrites upstream artifacts
- [ ] Every artifact includes: `status`, `blocking_issues`, `assumptions`, `open_questions`, `source_references`
- [ ] Schema validation passed (0 violations) for all artifacts written this stage
- [ ] Run-ledger updated with stage status and timestamps
- [ ] Agent run report filed (`docs/sops/templates/agent-run-report.md`)

---

**Checklist outcome:**

| Result | Meaning |
|--------|---------|
| All checked | Stage complete — advance to next stage |
| Any `FAIL` gate | Do NOT advance — resolve or escalate per `13-fallback-escalation.md` |
| `WARN` gates only | Advance with documented warn — note in run report |

---

*HyperEdit Pipeline QC | `docs/sops/templates/qc-checklist.md`*
