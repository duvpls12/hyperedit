# SOP: Photo-to-Video Generation (Conditional)

## Objective

Generate high-fidelity synthetic video clips from property stills to fill blocking coverage gaps that cannot be resolved with existing footage. Synthetic clips must be indistinguishable from real footage in color, motion, and realism.

## Trigger

Runs **only when** `12_gap_report.json` contains at least one gap with `type: "blocking"` and `fill_source: "stills"`. If no blocking gaps exist that stills can fill, skip this stage entirely and proceed to `04-audio-radio-edit.md`.

## Inputs

| Input | Source | Schema |
|-------|--------|--------|
| Gap report | `state/agents/<project_id>/12_gap_report.json` | `schemas/12_gap_report.schema.json` |
| Property photos (stills) | `brief.stills_dir` | JPEG/PNG, full resolution |
| Base color reference | Adjacent real clips from `11_selects_shortlist.json` | — |
| Style intent | `00_project_brief.json` → `style_intent` | — |

## Prerequisites

- `12_gap_report.json` exists with `status: "pass"` or `"warn"`.
- ComfyUI running on `localhost:8188` (local) or Vast.ai endpoint (remote) — see `09-comfyui-setup.md`.
- LTXVideo (LTX-2 19B) nodes installed in ComfyUI.
- IC-LoRA camera control nodes available.
- **Heavy generation (LTX-2 19B) routes to Vast.ai GPU**, not local Mac.

## Procedure

1. **Filter gap report to blocking gaps only.**
   - Parse `12_gap_report.json` — extract only entries where `type: "blocking"` and `fill_source: "stills"`.
   - Expected output: `generation_targets` list with gap_id, sequence_block, required_motion.

2. **Write `20_synthetic_plan.json`.**
   - For each target: record gap_id, source_still path, desired motion archetype, target duration, adjacent clip directions.
   - Confirm each is genuinely `blocking` — do not generate for non-blocking gaps.
   - Expected output: `state/agents/<project_id>/20_synthetic_plan.json`.

3. **Color-normalize source stills before export.**
   - Match exposure and white balance of source still to adjacent real clips.
   - Use color-matcher CLI: `color-matcher -s <still> -r <reference_frame>`.
   - Expected output: normalized stills saved to session temp directory.

4. **Build ComfyUI generation prompts.**
   - For each target: construct prompt with strict constraints:
     - Keep architecture geometry stable (no morphing walls/ceilings).
     - Preserve lens perspective of the still.
     - Match movement direction and speed from `synthetic_plan.motion_archetype`.
     - Avoid object hallucinations and temporal warping.
     - Conservative motion to reduce artifact risk.
   - Workflow: `skills/comfyui-workflows/image-to-video.json` (LTXVideo I2V + IC-LoRA).
   - Expected output: workflow JSON ready for dispatch.

5. **Dispatch to ComfyUI (Vast.ai GPU endpoint).**
   - `POST /prompt` with workflow JSON to remote ComfyUI endpoint.
   - Generate 2–3 variants per request for selection.
   - Poll `GET /history/{prompt_id}` until complete.
   - Download output clips to `state/agents/<project_id>/synthetic_raw/`.
   - Expected output: 2–3 raw generated clips per gap.

6. **Run realism QC on each generated clip.**
   - Check each variant:
     - Geometry consistency (no warping walls, floors, ceilings).
     - Motion plausibility (no impossible camera movement).
     - Lighting continuity (matches adjacent real clips).
     - Compression/artifact check (no visible AI artifacts).
   - Select best variant. Record rejection reasons for failed variants.
   - Expected output: per-clip QC result with selected variant and rejection log.

7. **Enforce synthetic usage ceiling.**
   - Synthetic clips must remain ≤ 20% of total final timeline duration.
   - If generating would exceed 20%: reduce to highest-priority blocking gaps only.
   - Expected output: `synthetic_plan.usage_pct` field.

8. **Write outputs and validate.**
   - Write `21_generated_clips.json` (approved clips with provenance metadata: tool, prompt, seed, model, ComfyUI node version).
   - Write `22_realism_qc.json` (per-clip pass/fail + rejection reasons for rejected variants).
   - Run schema validation: `scripts/validate-artifact.js`.
   - Expected output: all artifacts with `status: "pass"` or `"warn"`.

## Quality Gates

| Gate | Pass | Warn | Fail |
|------|------|------|------|
| All blocking gaps addressed | All resolved | 1 gap still blocking | >1 gap still blocking |
| No visible warping/flicker | 0 artifacts | — | Any visible artifact |
| Geometry consistency | Stable | Minor drift | Visible morph/warp |
| Motion plausibility | Natural | Slightly fast | Impossible motion |
| Lighting continuity match | ΔE < 5 | ΔE 5–10 | ΔE > 10 |
| Synthetic usage ≤ 20% | ≤ 20% | 21–25% | > 25% |
| Provenance metadata present | All clips | — | Any missing |

## Outputs

| Artifact | Path | Schema |
|----------|------|--------|
| Synthetic generation plan | `state/agents/<project_id>/20_synthetic_plan.json` | `schemas/20_synthetic_plan.schema.json` |
| Approved generated clips | `state/agents/<project_id>/21_generated_clips.json` | `schemas/21_generated_clips.schema.json` |
| Realism QC report | `state/agents/<project_id>/22_realism_qc.json` | `schemas/22_realism_qc.schema.json` |

## Failure Handling

- **Vast.ai GPU unavailable**: Queue generation task in run-ledger, continue with non-GPU stages (audio, assembly with placeholder gaps). Resume when GPU is available. See `13-fallback-escalation.md`.
- **All 3 variants fail QC**: Mark gap as `status: "fail"` in `22_realism_qc.json`. Surface to Orchestrator — may need to try alternate source still or accept gap.
- **ComfyUI LTXVideo node error**: Check node installation at `hyperedit-deps/ComfyUI-LTXVideo/`. See `09-comfyui-setup.md` for node verification.
- **Retry policy**: Max 2 generation retries per gap. On persistent failure, write `blocking_issues` and escalate.
- **Escalation**: Orchestrator may override and mark gap as `accepted_warn` to unblock assembly.

## Downstream Dependencies

Completing this SOP unblocks:
- `05-assembly-picture-lock.md` (Assembly reads `21_generated_clips.json` as optional input)

## Skill Cross-Reference

- Skill: `skills/hyperedit-agent-image-to-video/SKILL.md`
- Procedure matches: `skills/hyperedit-agent-image-to-video/SOP.md` Steps 1–8
- Context: `skills/hyperedit-agent-image-to-video/CONTEXT.md`
- ComfyUI workflow: `skills/comfyui-workflows/image-to-video.json`
- Tool: ComfyUI + LTXVideo nodes at `hyperedit-deps/ComfyUI-LTXVideo/`
