# SOP 08 — Agent Context Linking (HyperEdit local repo)

## Purpose
Ensure each process actor references a single assignment source of truth.

## Source of truth
- Assignment matrix: `docs/sops/07-agent-skill-sop-assignment.md`

## Linking policy
For each agent context pack (AGENT(S).md / TOOLS.md / MEMORY.md / CONTEXT.md):
1. Add a **Process Assignment** section.
2. Link to `docs/sops/07-agent-skill-sop-assignment.md`.
3. State that skill/SOP mapping in that file is authoritative.
4. Require SOP-first execution and deterministic outputs.

## Required statement block
Use this exact block in each agent context doc:

```md
## Process Assignment
- Authoritative mapping: `docs/sops/07-agent-skill-sop-assignment.md`
- This agent must execute assigned SOPs/skills exactly as defined in the mapping.
- Deterministic output required: artifact paths, gate outcomes, blockers, commit hash.
```

## Current state
- Local hyperedit repo currently has no dedicated per-agent context files at root level.
- Until agent context packs are created locally, use this SOP + `07-agent-skill-sop-assignment.md` as policy source.
