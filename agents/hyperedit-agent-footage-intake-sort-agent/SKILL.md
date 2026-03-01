---
name: hyperedit-agent-footage-intake-sort
description: Ingest and sort footage into sequence-ready selects with continuity and gap reporting.
metadata:
  tags: hyperedit,footage,sorting,editing
---

# Footage Intake and Sorting Skill

## When to use

Use this skill at the start of every project before assembly editing.

## Use this workflow

1. Read `CONTEXT.md` to apply tutorial based selection heuristics.
2. Run `SOP.md` to produce catalogs, selects, and gap report.
3. Hand off outputs to assembly agent and optional image-to-video agent.

## Claude Code trigger

Invoke as `/hyperedit-footage-intake` or when the orchestrator dispatches this stage at pipeline start.

## Proxy-First Workflow

Footage intake now generates lightweight **720p H.264 proxies** for every clip. All downstream editing (assembly, review, QC) happens on proxies. Full-resolution footage is only touched at the final conform + grade stage after picture lock. This saves significant processing time and GPU cost since not all clips make the final cut.

**Flow:**
1. Classify each clip (vision model on GPU)
2. Sort into bins (symlink)
3. Generate 720p proxy (`proxies/{clip_id}_proxy.mp4`)
4. Assembly agent works exclusively with proxy files
5. After picture lock → Color agent conforms: replaces proxies with full-res, applies LUT + grade

## Tools

- **FFmpeg server** (`localhost:3333`): Upload clips via `POST /session/{id}/assets` for metadata extraction and thumbnail generation
- **ComfyUI VideoHelperSuite** (local `:8188`): Extract frames per clip for vision analysis (`Load Video (Upload)` node)
- **Ollama vision model** (Vast.ai GPU or local): Shot class tagging via `qwen2.5vl:7b` — submit extracted frame, receive classification JSON
- **FFmpeg** (local): Proxy generation — `ffmpeg -i input.mp4 -vf "scale=720:-2" -c:v libx264 -crf 23 -preset ultrafast -c:a aac -b:a 128k output_proxy.mp4`
- **video2x** (optional): AI upscale low-res clips before assembly — `video2x -i clip.mp4 -o out.mp4 --scale-factor 2`

### Pipeline Scripts

| Script | Purpose | When to use |
|--------|---------|-------------|
| `scripts/run-pipeline-remote.js` | SCP clips to Vast.ai GPU, classify server-side, generate proxies locally | **Primary** — fastest, offloads decode to GPU |
| `scripts/run-pipeline-local.js --classify-only` | Classify via Ollama tunnel (localhost:8080), no grading | When SSH upload is slow or clips are small |
| `scripts/run-pipeline-local.js --grade-only` | Grade previously classified clips from shot-catalog.json | Post picture-lock conform |
| `scripts/bridge-catalog.js` | Transforms `shot-catalog.json` → `10_footage_catalog.json` + `11_selects_shortlist.json` with schema mapping, coverage enforcement, usability scoring | After classification, before orchestrator |
| `scripts/generate-proxies.js` | 720p H.264 CRF 23 proxy generation with concurrency 4, ~5s/clip | After classification, or standalone |
| `scripts/grade-pipeline.js` | Benchmarks AI classification against human editor's final cut. Computes precision/recall/F1/letter grade. Supports `--edit list:file.txt`, `--edit clips-dir:path`, `--edit clipwise:session-id`, `--edit premiere:xml` | Post-edit verification / accuracy benchmarking |

## State paths

- Reads: `state/agents/<project_id>/00_project_brief.json`, raw footage directory
- Writes: `state/agents/<project_id>/10_footage_catalog.json`, `state/agents/<project_id>/11_selects_shortlist.json`, `state/agents/<project_id>/12_gap_report.json`

## Camera-Aware Drone Override Rule

Only filenames prefixed with `DJI_` can classify as `drone`. If a non-DJI clip is classified as drone by the vision model, it is reclassified to `wide`. This rule is enforced in `run-pipeline-local.js`, `run-pipeline-remote.js`, `gpu-classify.py`, `hyperedit-mcp-server.js`, and `bridge-catalog.js`.

## Project folder outputs

- `bins/` — Symlinks to raw footage, organized by classification (wide/, detail/, drone/, etc.)
- `proxies/` — 720p H.264 CRF 23 proxy files for editing
- `shot-catalog.json` — Full classification metadata per clip (camera, color profile, bin, LUT path)

## Required outputs

- `10_footage_catalog.json`
- `11_selects_shortlist.json`
- `12_gap_report.json`
