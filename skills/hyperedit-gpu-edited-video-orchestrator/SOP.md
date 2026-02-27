# SOP - GPU Edited-Video Orchestrator

## Objective

Eliminate idle GPU time by sequencing edited-video-only jobs with strict checkpoints and backfill behavior.

## Inputs

- Final edited video files.
- Existing transcript corpus.
- Existing analysis JSON (if any).
- Runtime budget and target stop time.

## Queue phases

1. `phase_1_pattern_mining`
- Shot boundaries, camera motion classes, pacing signatures, hook/rehook markers.

2. `phase_2_style_benchmark`
- Cross-video clustering by pacing, transitions, color intent, sound density.

3. `phase_3_rag_index`
- Embed transcripts + mined JSON + benchmark outputs into local RAG.

4. `phase_4_training_dataset`
- Build agent-ready examples, rules, and anti-pattern datasets.

## Throughput policy

- Always keep one GPU-heavy and one CPU/lightweight post-process task paired.
- If a phase stalls, backfill with next-video jobs from same phase.
- Write checkpoint every 5-10 minutes.
- Never run a single long job without heartbeat logging.

## Failure handling

- On model/API failure, retry with reduced batch size and context window.
- On repeated parse failures, persist raw output and mark for offline repair.
- On OOM, downscale frame sampling density before retrying.

## Required outputs

- `state/gpu-edited-video/<run_id>/queue_state.json`
- `state/gpu-edited-video/<run_id>/phase_summary.md`
- `state/gpu-edited-video/<run_id>/handoff.md`
