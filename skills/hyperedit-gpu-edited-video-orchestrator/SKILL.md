---
name: hyperedit-gpu-edited-video-orchestrator
description: No-idle orchestration for GPU runs when only final edited videos are available.
metadata:
  tags: hyperedit,gpu,orchestration,edited-video
---

# HyperEdit GPU Edited-Video Orchestrator

## Objective

Keep rented GPU utilization high when raw clips are unavailable by running a deterministic queue of high-value jobs on edited videos.

## Use this sequence

1. Read `CONTEXT.md`.
2. Execute `SOP.md`.
3. Produce run artifacts in `state/gpu-edited-video/<run_id>/`.
4. Dispatch downstream skills:
- `hyperedit-gpu-edited-video-pattern-mining`
- `hyperedit-gpu-style-benchmark`
- `hyperedit-gpu-rag-index-build`
- `hyperedit-gpu-agent-training-dataset`
