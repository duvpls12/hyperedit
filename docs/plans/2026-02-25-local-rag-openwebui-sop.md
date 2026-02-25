# SOP — Local RAG with OpenWebUI for HyperEdit

## Objective
Create a local-only retrieval layer so HyperEdit can query prior analyses, assessments, and rules quickly and consistently.

## Stack
- OpenWebUI (UI/chat)
- Qdrant (vector database)
- Local embedding endpoint (OpenAI-compatible `/v1/embeddings`)

## Location
- `/Users/davideby/hyperedit/rag-local`

## Steps
1. Start Docker services (`docker compose up -d`).
2. Configure embedding env (`.env`).
3. Run ingestion script (`scripts/index_hyperedit.py`).
4. Query via OpenWebUI against indexed artifacts.

## Indexed Data Scope
- `state/video-analysis-single/*.json`
- `state/audio-analysis/*.json`
- `state/final-analysis/*.md`
- `docs/plans/*.md`

## Metadata Policy
Payload fields:
- `source`
- `chunk_index`
- `video_id`
- `ext`
- `text`

## Expected Outcomes
- Faster cross-video pattern retrieval.
- Better consistency in deriving rules/guidelines from 20/100-video cohorts.
- Local-only data boundary preserved.
