# Context - Image to Video Generation

## Source patterns from tutorials

- AI lot workflow: build timeline first, then derive start/end frames for generation.
- Color normalize before frame export; ungraded inputs produce mismatched generations.
- Stabilize and time plan first, then generate against real beat timing.
- Use AI to extend storytelling where footage is missing, not as a default replacement.

## Practical heuristics

- Generate for transitions, lot visualization, or missing detail bridges.
- Keep generated shots short and purposeful.
- Match movement archetypes from surrounding real clips (`push`, `orbit`, `slider`).
- Prefer conservative motion to reduce artifact risk.

## Failure modes

- Synthetic frame style mismatch due to skipped base grade.
- Over dramatic prompt language producing unrealistic motion.
- Ignoring neighboring shot direction causing continuity break.
- Excess synthetic coverage reducing viewer trust.

## Governance

- Every generated clip needs provenance metadata (tool, prompt, seed, model).
- Every rejected generation should include failure reason for future RAG learning.
