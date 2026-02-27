# Context - RAG Index Build

## Edited-video-only focus

When raw assets are missing, retrieval quality depends on clear extraction schemas and metadata-rich chunks.

## Indexing heuristics

- Prefer semantic chunks over arbitrary token windows.
- Keep source references for auditability.
- Include confidence and provenance to reduce hallucinated rules.

## Quality risks

- Duplicate chunks causing noisy retrieval.
- Missing metadata leading to wrong archetype matches.
- Embedding stale outputs without versioning.
