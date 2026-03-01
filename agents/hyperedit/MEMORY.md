# MEMORY.md — hyperedit

## Durable context
- HyperEdit prioritizes reliable ingest → processing → delivery.
- Preserve decisions and root causes for recurring failures.
- Orchestrator SOPs/skills scope: intake, analysis, QA, RAG, health, exceptions, reporting.
- Grading workflow: run checks → score rubric → apply penalties → pass/fail → rerun or RAG commit.
- Approvals required for delete/move and disk cleanup/archive.
- Grading artifacts stored at ~/hyperedit/state/intel/grades.
- Orchestrator SOPs/skills live at ~/hyperedit/docs/sops and ~/hyperedit/skills/hyperedit-orchestrator.
- Custom notes tool requested: Frame.io-style (timestamped comments, markup, threaded approvals, versioning).
- Dedicated coding agent folder: ~/clawd-main/agents/hyper-edit/hyper-edit coding (Codex 5.3 + Claude Code CLI; no /tmp).
- Enforcement directive: follow SOPs and skills exactly as written for QA/recreate loops; deterministic outputs only and no proxy claims without explicit limitation labels.
- [2026-03-01T04:47:59Z] Autonomy directive: continue end-to-end QA/recreate execution with periodic local+supermemory checkpoints; escalate only hard blockers/risky actions.
