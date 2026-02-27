# Context - Edited-Video Pattern Mining

## Why this works without raw clips

Final edits still preserve decisions that matter:
- sequencing
- pacing
- transition usage
- audio-visual synchronization
- hook/payoff structure

## Extraction priorities

- Favor timeline-level signals over per-pixel perfection.
- Keep schemas stable so downstream training and RAG can reuse outputs.
- Track confidence for every inferred pattern.

## Common risks

- Over-interpreting ambiguous transitions.
- Confusing camera movement with post zoom/rotation effects.
- Failing to align audio accents with transition events.
