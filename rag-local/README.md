# HyperEdit Local RAG (OpenWebUI + Qdrant)

## Start services
```bash
cd /Users/davideby/hyperedit/rag-local
docker compose up -d
```

- OpenWebUI: http://localhost:3000
- Qdrant: http://localhost:6333

## Configure embeddings
Copy env template:
```bash
cp .env.example .env
```

Set `EMBEDDING_BASE_URL` to your local embedding endpoint (LM Studio/Ollama OpenAI-compatible `/v1`).

## Ingest HyperEdit artifacts
```bash
cd /Users/davideby/hyperedit/rag-local
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
set -a; source .env; set +a
python scripts/index_hyperedit.py
```

## Indexed sources
- `state/video-analysis-single/*.json`
- `state/audio-analysis/*.json`
- `state/final-analysis/*.md`
- `docs/plans/*.md`

## Retrieval starter prompts
- "Show recurring hook timing patterns across final synthesis reports."
- "Find repeated shot sequencing motifs for luxury exteriors."
- "Compare audio BPM/energy patterns with transition guidance."
- "Summarize strongest recurring QA flags across assessments."
