# Context - Agent Training Dataset

## Purpose

This stage turns extracted intelligence into actionable training data so the system improves before new raw footage arrives.

## Design principles

- Keep examples stage-specific and deterministic.
- Include anti-patterns so agents learn what to avoid.
- Preserve direct links to source evidence.

## Risks

- Training on low-confidence rules.
- Over-generalizing from small sample sets.
- Missing failure and recovery cases.
