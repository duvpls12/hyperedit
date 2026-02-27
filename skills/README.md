# HyperEdit Skills

These skills are in Claude Code-recognized format:

- folder: `skills/<skill-name>/`
- required file: `SKILL.md`
- optional support files: `SOP.md`, `CONTEXT.md`

## Editing Pipeline Skills (Pipeline A)

- `hyperedit-agent-master-orchestrator` — Dispatch all agents, QA/grade output
- `hyperedit-agent-footage-intake-sort` — Ingest, tag, sort, shortlist raw media
- `hyperedit-agent-image-to-video` — Generate synthetic clips from stills (conditional)
- `hyperedit-agent-audio-sound-design` — Music selection, BPM analysis, radio edit (runs BEFORE assembly)
- `hyperedit-agent-assembly-editor` — Build timeline from music map + shot pool → picture lock
- `hyperedit-agent-color-pipeline` — Correction + creative grading (runs AFTER picture lock)
- `hyperedit-agent-graphics-captions` — Captions, lower thirds, motion graphics (conditional)

## GPU Learning Pipeline Skills (Pipeline B)

- `hyperedit-gpu-edited-video-orchestrator` — No-idle GPU queue orchestrator
- `hyperedit-gpu-edited-video-pattern-mining` — Mine shot structure, pacing, hook/rehook patterns
- `hyperedit-gpu-style-benchmark` — Cluster and benchmark editing styles
- `hyperedit-gpu-rag-index-build` — Build local RAG indexes from patterns + transcripts
- `hyperedit-gpu-agent-training-dataset` — Synthesize training datasets for editing agents

## Infrastructure Skills

- `hyperedit-remote-gpu-vastai` — Remote GPU dispatch to Vast.ai
- `hyperedit-two-pass-vision-audio` — Hybrid ingest runner (two-pass vision + audio)

## Utility Skills

- `remotion-best-practices` — Domain-specific Remotion knowledge for motion graphics

## ComfyUI Workflow Templates

- `comfyui-workflows/` — JSON workflow templates for ComfyUI dispatch
