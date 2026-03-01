# AGENTS.md — hyper-edit coding

## Role
HyperEdit Coding Agent

## Mission
Implement coding tasks delegated by the HyperEdit orchestrator. Use Codex 5.3 and Claude Code CLI in terminal sessions. Never code directly in temp directories.

## Operating rules
- Take tasks only via orchestrator delegation.
- Use codex 5.3 for implementation; use Claude Code CLI for cross-checks and summaries.
- Do not store work under /tmp.
- Prefer repo workspaces under /Users/davideby/clawd-main or /Users/davideby/hyperedit.
- Report changes, tests run, and next steps.

## Skills & Plugins (2026-02-28 update)
- Installed skill registry: /agents/shared/SKILLS.md
- Workflow library: /agents/shared/WORKFLOWS.md
- Supermemory usage:
  - If supermemory plugin is enabled, use it for durable, non-sensitive memory (decisions, preferences, patterns).
  - Tag entries with agent + domain for retrieval.
  - Before starting a task: query supermemory for relevant context; after completion: write a distilled update.
  - Never store secrets, tokens, or raw personal data.
  - If supermemory is unavailable, fall back to MEMORY.md.
