---
name: hyperedit-orchestrator
description: Run the full HyperEdit 7-stage editing pipeline from a client brief to a publish-ready video. Dispatches all specialist agents in dependency order with quality gates, artifact validation, and run-ledger state tracking.
metadata:
  tags: hyperedit,orchestrator,pipeline,dispatch
---

# HyperEdit Orchestrator Skill

## When to use

Use this skill when:
- The user provides a client brief and says something like "run project", "edit this property", or "start the pipeline"
- Resuming an interrupted project from a run-ledger checkpoint
- Re-running a failed stage after fixing a blocker

## Claude Code trigger

Invoke as `/hyperedit-orchestrator` or `/hyperedit-run`.

## How to use

1. Read [CONTEXT.md](CONTEXT.md) for pipeline heuristics and decision rules.
2. Execute [SOP.md](SOP.md) step-by-step to dispatch the full pipeline.

## Pipeline order (hard dependency chain)

```
ORCHESTRATOR (init)
  → FOOTAGE INTAKE    (always — classify + sort + generate 720p proxies)
  → PHOTO-TO-VIDEO    (conditional: only if 12_gap_report has blocking gaps)
  → AUDIO             (always, must run BEFORE assembly)
  → ASSEMBLER         (always, uses PROXY files — reads 30_music_map + 31_radio_edit)
  → COLOR + CONFORM   (always, only after 42_picture_lock — replaces proxies with graded full-res)
  → TEXT & GRAPHICS   (conditional: only if brief specifies captions=true)
ORCHESTRATOR (QA)
```

### Proxy-First Workflow

All editing happens on lightweight 720p H.264 proxies. This keeps assembly fast and avoids processing 4K/HEVC footage during the creative phase. Only clips that make the final cut get graded at full resolution during the Color + Conform stage. This saves significant processing time and GPU cost.

```
Footage Intake → classify → sort → generate 720p proxies
Assembly       → edit timeline using proxy files only
Color+Conform  → replace proxies with full-res → apply LUT + grade → only final cut clips
```

## State paths

- Run-ledger: `state/run-ledger/<project_id>.json`
- Artifacts: `state/agents/<project_id>/`
- Schemas: `schemas/`
- Validation: `scripts/validate-artifact.js`

## Required outputs

- `state/run-ledger/<project_id>.json`
- `state/agents/<project_id>/00_project_brief.json`
- `state/agents/<project_id>/01_orchestration_plan.json`
- `state/agents/<project_id>/70_final_qc_report.json`
- `state/agents/<project_id>/71_grade_card.json`
- `state/agents/<project_id>/72_publish_checklist.json`

## Shared references

- System overview: [docs/agents/README.md](../../docs/agents/README.md)
- IO contract: [docs/agents/agent_io_contract.md](../../docs/agents/agent_io_contract.md)
- Run-ledger schema: [schemas/run-ledger.schema.json](../../schemas/run-ledger.schema.json)
