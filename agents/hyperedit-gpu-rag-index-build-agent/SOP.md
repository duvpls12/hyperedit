# SOP - RAG Index Build

## Inputs

- Transcript markdown/txt.
- Pattern mining JSON.
- Style benchmark outputs.
- Existing context/SOP docs.

## Procedure

1. Build canonical corpus bundle with metadata.
2. Chunk by semantic unit:
- workflow step
- pattern rule
- failure mode
- benchmark finding
3. Attach metadata tags:
- `video_type`, `platform`, `agent_stage`, `property_style`, `confidence`
4. Generate embeddings and index collections:
- `tutorial_core`
- `edited_video_patterns`
- `style_benchmarks`
- `agent_sops`
5. Run retrieval tests for representative prompts.
6. Log precision/recall notes and patch chunking if needed.

## Outputs

- `corpus_bundle.json`
- `rag_index_manifest.json`
- `retrieval_eval.md`
