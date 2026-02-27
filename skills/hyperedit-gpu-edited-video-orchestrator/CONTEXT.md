# Context - GPU Edited-Video Orchestrator

## Constraint model

- No raw clips available.
- Inputs are final edited exports only.
- Goal is to extract reusable editing intelligence and training signals.

## Highest-value outputs under this constraint

- Hook/rehook timing distributions.
- Cut cadence and speed-ramp placement patterns.
- Directional flow and transition archetypes.
- Color and audio style fingerprints.
- RAG-ready rule chunks tied to empirical outcomes.

## No-idle guardrails

- Use micro-batches to avoid long failure windows.
- Keep phase outputs schema-validated before next phase.
- Prioritize high-confidence extraction tasks first.

## Completion criteria

Run is complete when all phases have summaries, QC status, and indexed outputs or explicit blockers.
