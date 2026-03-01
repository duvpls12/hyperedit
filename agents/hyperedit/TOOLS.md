# TOOLS.md — hyperedit

## Preferred tools
- exec/process for pipeline ops
- cron for recurring checks and reminders
- sessions_spawn for parallel investigations
- read/write/edit for SOP/skill maintenance

## Skills & Plugins (2026-02-28 update)
- Authoritative list: /agents/shared/SKILLS.md
- Workflow library: /agents/shared/WORKFLOWS.md
- Prefer first-class skills before bespoke scripts.
- Supermemory plugin (if enabled) for durable notes; otherwise use MEMORY.md.

## Memory Output Policy (QMD-first local)
- Save durable QA/recreate loop context to markdown (QMD-style local docs) under:
  - `agents/hyperedit/memory/`
  - `state/baseline/<project>/`
  - `state/agents/<project_id>/`
- Supermemory is additive sync, not a single point of failure.
- For cron memory runs, prefer committing only the intended log artifact unless explicitly approved otherwise.

## QA / SOP Execution Defaults
- Use `skills/hyperedit-qc-gate/SKILL.md` + `SOP.md` for stage gating.
- Execute SOPs/skills as written; no ad-hoc substitutions unless explicitly approved.
- Always produce structured gate outputs (`*_qc_result.json`) before declaring pass.
- Never report final quality status without required artifacts present for that stage.
- Use provider fallback matrix for QA/Vision/Audio when runtime providers fail.
- If running degraded/proxy mode, mark it explicitly and schedule a real artifact re-run.
