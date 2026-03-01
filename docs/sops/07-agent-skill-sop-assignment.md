# SOP 07 — Agent ↔ Skill ↔ SOP Assignment Matrix

## Purpose
Map each HyperEdit process agent to the exact skills and SOPs it must use.

## Source of truth
- Skills root: `/Users/davideby/hyperedit/skills`
- SOP root: `agents/hyperedit/docs/sops`

## Assignment Matrix

| Process Agent | Primary Skills | Required SOPs |
|---|---|---|
| Master Orchestrator | `hyperedit-agent-master-orchestrator`, `hyperedit-orchestrator`, `hyperedit-qc-gate`, `hyperedit-gpu-edited-video-orchestrator` | `00-orchestrator-index.md`, `01-intake-staging.md`, `02-grading-workflow.md`, `03-exception-reruns.md`, `04-rag-indexing-retrieval.md`, `provider-fallback-matrix.md` |
| Footage Intake/Sort Agent | `hyperedit-agent-footage-intake-sort` | `01-intake-staging.md`, `03-exception-reruns.md`, `provider-fallback-matrix.md` |
| Image-to-Video Agent | `hyperedit-agent-image-to-video`, `comfyui-workflows` | `01-intake-staging.md`, `03-exception-reruns.md`, `provider-fallback-matrix.md` |
| Audio/Sound Design Agent | `hyperedit-agent-audio-sound-design`, `hyperedit-two-pass-vision-audio` | `06-audio-subagent-workflow.md`, `02-grading-workflow.md`, `provider-fallback-matrix.md` |
| Assembly Editor Agent | `hyperedit-agent-assembly-editor`, `hyperedit-two-pass-vision-audio` | `05-assembler-workflow.md`, `02-grading-workflow.md`, `03-exception-reruns.md`, `provider-fallback-matrix.md` |
| Color Pipeline Agent | `hyperedit-agent-color-pipeline` | `02-grading-workflow.md`, `03-exception-reruns.md`, `provider-fallback-matrix.md` |
| Graphics/Captions Agent | `hyperedit-agent-graphics-captions`, `remotion-best-practices` | `02-grading-workflow.md`, `03-exception-reruns.md` |
| QC Gate Agent | `hyperedit-qc-gate` | `02-grading-workflow.md`, `03-exception-reruns.md`, `provider-fallback-matrix.md` |
| GPU Edited Video Orchestrator | `hyperedit-gpu-edited-video-orchestrator`, `hyperedit-remote-gpu-vastai` | `00-orchestrator-index.md`, `03-exception-reruns.md`, `provider-fallback-matrix.md` |
| GPU Pattern Mining Agent | `hyperedit-gpu-edited-video-pattern-mining`, `hyperedit-gpu-style-benchmark` | `02-grading-workflow.md`, `04-rag-indexing-retrieval.md` |
| GPU Training Dataset Agent | `hyperedit-gpu-agent-training-dataset` | `02-grading-workflow.md`, `04-rag-indexing-retrieval.md` |
| GPU RAG Index Agent | `hyperedit-gpu-rag-index-build` | `04-rag-indexing-retrieval.md`, `02-grading-workflow.md` |
| Hyper-Edit Coding Agent | `hyperedit-orchestrator` (dispatch policy), terminal Codex/Claude workflow | `00-orchestrator-index.md`, `03-exception-reruns.md`, `provider-fallback-matrix.md` |

## Explicit local agents in this repo

### `agents/hyper-edit/hyper-edit assembler`
- Assigned skills:
  - `hyperedit-agent-assembly-editor`
  - `hyperedit-two-pass-vision-audio`
  - `hyperedit-qc-gate`
- Required SOPs:
  - `05-assembler-workflow.md`
  - `06-audio-subagent-workflow.md`
  - `02-grading-workflow.md`
  - `03-exception-reruns.md`
  - `provider-fallback-matrix.md`

### `agents/hyper-edit/hyper-edit coding`
- Assigned skills:
  - `hyperedit-orchestrator` (task contract/dispatch)
- Required SOPs:
  - `00-orchestrator-index.md`
  - `03-exception-reruns.md`
  - `provider-fallback-matrix.md`

## Enforcement rules
1. Agents must execute assigned SOPs before claiming completion.
2. `02-grading-workflow.md` gate is mandatory before any RAG commit.
3. Provider failures must follow `provider-fallback-matrix.md`.
4. Any proxy/degraded run must be explicitly labeled in outputs.
