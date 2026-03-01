# SOP - Agent Training Dataset Synthesis

## Inputs

- Pattern mining outputs.
- Style benchmark outputs.
- Existing SOP/context documents.

## Procedure

1. Create task templates by agent stage:
- footage planning
- assembly sequencing
- color correction/grading
- graphics/caption decisions
- audio design decisions
2. Convert rules into examples:
- positive examples (what to do)
- negative examples (anti-patterns)
- recovery examples (what to do when constraints fail)
3. Build evaluation sets:
- rubric-based expected outputs
- pass/fail checks
4. Add provenance fields and confidence scores.
5. Export versioned dataset package.

## Outputs

- `agent_training_examples.jsonl`
- `agent_eval_set.json`
- `rulebook_delta.md`
