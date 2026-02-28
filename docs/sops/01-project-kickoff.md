# SOP: Project Kickoff & Brief Intake

## Objective

Initialize a new video project from a client brief: create the project skeleton, define quality gates, and produce the orchestration plan that dispatches all downstream agents in dependency order.

## Trigger

Run when the user provides a client brief or invokes `/hyperedit-run <brief>`. This is always the first stage in every pipeline run.

## Inputs

| Input | Source | Schema |
|-------|--------|--------|
| Client brief (JSON or natural language) | User / PM dashboard | `docs/sops/templates/project-brief-template.json` |
| Target platform | Brief | `reel` \| `mls` \| `signature` \| `ai_lot` |
| Source footage directory path | Brief | Filesystem path |
| Brand constraints | Brief | Colors, fonts, tone rules |
| Runtime target | Brief | Seconds (e.g., 30, 60, 90) |

## Prerequisites

- No upstream artifacts required (this is Stage 0).
- `state/agents/` directory must be writable.
- `state/run-ledger/` directory must exist.
- `schemas/00_project_brief.schema.json` must be present for validation.

## Procedure

1. **Parse and validate client brief.**
   - Normalize to `00_project_brief.json` using `schemas/00_project_brief.schema.json`.
   - Confirm required fields: `project_id`, `property_address`, `footage_directory`, `target_duration_seconds`, `delivery_format`.
   - Expected output: `state/agents/<project_id>/00_project_brief.json` with `status: "pass"`.

2. **Create project skeleton.**
   - Create directory `state/agents/<project_id>/`.
   - Write `00_project_brief.json`.
   - Expected output: directory exists, brief written.

3. **Initialize run-ledger.**
   - Write `state/run-ledger/<project_id>.json` with all 8 stages initialized as `pending`.
   - Stage names (snake_case per schema): `orchestrator_init`, `footage_intake`, `photo_to_video`, `audio`, `assembly`, `color`, `text_graphics`, `orchestrator_qc`.
   - Expected output: run-ledger written with `current_stage: "orchestrator_init"`.

4. **Define quality gates.**
   - Read `skills/hyperedit-agent-master-orchestrator/CONTEXT.md` for gate parameters.
   - Write `01_orchestration_plan.json` with per-stage gate definitions, retry limits (max 2), and dependency map.
   - Expected output: `state/agents/<project_id>/01_orchestration_plan.json`.

5. **Select pipeline variant.**
   - If `format_target == "ai_lot"`: mark `photo_to_video` as `enabled: true`.
   - If client brief has `caption_required: true`: mark `text_graphics` as `enabled: true`.
   - Default: `photo_to_video` and `text_graphics` are `enabled: false` (conditional).
   - Proxy workflow is **always enabled** — assembly uses 720p proxies, conform+grade happens after picture lock.
   - Expected output: orchestration plan updated with enabled flags.

6. **Dispatch Footage Intake.**
   - Invoke `skills/hyperedit-agent-footage-intake-sort/` skill with `project_id` and `footage_directory`.
   - Update run-ledger: `footage_intake → in_progress`.
   - Expected output: handoff to Footage Intake agent.

## Quality Gates

| Gate | Pass | Warn | Fail |
|------|------|------|------|
| Brief has all required fields | All present | Missing optional fields | Missing required fields |
| `delivery_format` fields valid | All valid | — | Invalid enum value |
| `footage_directory` exists on disk | Exists | — | Path not found |
| Run-ledger written | Present | — | Write error |
| Schema validation | 0 violations | — | Any violation |

## Outputs

| Artifact | Path | Schema |
|----------|------|--------|
| Project brief | `state/agents/<project_id>/00_project_brief.json` | `schemas/00_project_brief.schema.json` |
| Orchestration plan | `state/agents/<project_id>/01_orchestration_plan.json` | `schemas/01_orchestration_plan.schema.json` |
| Run-ledger | `state/run-ledger/<project_id>.json` | `schemas/run-ledger.schema.json` |

## Failure Handling

- **Missing required brief fields**: Return `BLOCKED: missing fields [list]`. Do not create skeleton. Ask user to complete brief using `docs/sops/templates/project-brief-template.json`.
- **Footage directory not found**: Return `BLOCKED: footage_directory not found`. Do not proceed.
- **Schema validation failure**: Log violations, return `BLOCKED: schema violations [list]`.
- **Retry policy**: No retries for kickoff — fix input and re-run.
- **Escalation**: If blocked after 1 attempt, surface to user with specific error and template link.

## Downstream Dependencies

Completing this SOP unblocks:
- `02-footage-ingest.md` (Footage Intake agent)
- All subsequent stages (via run-ledger dependency gating)

## Skill Cross-Reference

- Skill: `skills/hyperedit-orchestrator/SKILL.md`
- Procedure matches: `skills/hyperedit-orchestrator/SOP.md` Steps 1–6 _(SOP.md is a Wave 4 deliverable — pending Task #4)_
- Context: `skills/hyperedit-agent-master-orchestrator/CONTEXT.md`
