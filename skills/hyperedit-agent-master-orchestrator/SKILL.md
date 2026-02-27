---
name: hyperedit-agent-master-orchestrator
description: Coordinate the full real estate video pipeline across specialist subagents with deterministic handoffs and quality gates.
metadata:
  tags: hyperedit,orchestration,video,real-estate
---

# Master Orchestrator Skill

## When to use

Use this skill when a video project needs multi stage delegation across footage, synthetic generation, assembly, color, graphics, and audio.

## Execution order

1. Read `CONTEXT.md` for decision rules.
2. Run `SOP.md` to generate plan and gate definitions.
3. Dispatch subagent tasks in strict dependency order.
4. Aggregate QC and decide pass/fail/rework.

## Required outputs

Write orchestration artifacts to `state/agents/<project_id>/` using contracts in:

- [docs/agents/agent_io_contract.md](../../docs/agents/agent_io_contract.md)

## Subagent dependencies

- `hyperedit-agent-footage-intake-sort`
- `hyperedit-agent-image-to-video`
- `hyperedit-agent-audio-sound-design`
- `hyperedit-agent-assembly-editor`
- `hyperedit-agent-color-pipeline`
- `hyperedit-agent-graphics-captions`

## Shared references

- System overview: [docs/agents/README.md](../../docs/agents/README.md)
- Tutorial mapping: [docs/agents/tutorial_signal_map.md](../../docs/agents/tutorial_signal_map.md)
- RAG backlog: [docs/agents/rag_expansion_backlog.md](../../docs/agents/rag_expansion_backlog.md)
