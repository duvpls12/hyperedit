# SOP: RAG Commit Pipeline

## Objective

Commit completed pipeline stage outputs — artifacts, patterns, failure reasons, and QC results — to the local RAG index for persistent editing intelligence. Build a continuously improving knowledge base that informs future project runs.

## Trigger

Invoked by Orchestrator automatically after each stage completes with `status: "pass"` or `"warn"`. Also invoked manually after final QC to commit the complete project record.

## Inputs

| Input | Source | Schema |
|-------|--------|--------|
| Stage artifact(s) | `state/agents/<project_id>/` | Per-stage schemas |
| Stage name | Run-ledger `current_stage` | String |
| QC results | Stage QC artifact (e.g., `32_audio_qc.json`) | Per-stage QC schema |
| Rejection logs | Artifact `rejection_reasons[]` field | — |
| Project metadata | `00_project_brief.json` | `schemas/00_project_brief.schema.json` |

## Prerequisites

- RAG stack running: OpenWebUI + Qdrant at `rag-local/`.
- `skills/hyperedit-rag-commit/` skill installed.
- Stage artifact validated (not failed — failed artifacts are committed as failure records only).
- Qdrant vector database accessible.

## Procedure

1. **Start RAG stack (if not running).**

   **Option A — Docker (full stack with OpenWebUI):**
   ```bash
   cd /Users/davideby/hyperedit/rag-local
   docker compose up -d
   ```
   - Verify: OpenWebUI at `localhost:3000`, Qdrant at `localhost:6333`.

   **Option B — Fast local path (no Docker, LM Studio only):**
   ```bash
   cd /Users/davideby/hyperedit/rag-local
   python3 -m venv .venv && source .venv/bin/activate
   pip install -r requirements.txt
   python scripts/build_lmstudio_rag.py   # build index
   python scripts/query_lmstudio_rag.py "<query>"  # query index
   ```
   - Uses `LM_STUDIO_BASE_URL` + `LM_STUDIO_API_KEY` from `/Users/davideby/hyperedit/.env`.

   - Expected output: RAG stack or local index accessible.

2. **Prepare commit payload.**
   - Load stage artifact JSON.
   - Extract commit-worthy fields:
     - Stage name, project_id, format_target.
     - Status (pass/warn/fail), blocking_issues, assumptions.
     - Key decisions (e.g., selected music track, color LUT used, shot selection rationale).
     - QC results: per-gate pass/warn/fail.
     - Rejection reasons from failed variants (e.g., generated clip rejections in photo-to-video).
     - Source references.
   - Expected output: structured commit payload.

3. **Apply semantic chunking.**
   - Split payload into semantic chunks by category:
     - `workflow_step`: procedure decisions, tool invocations, parameter choices.
     - `heuristic`: domain rules applied (e.g., "hook in first 5s", "directional continuity").
     - `failure_mode`: blocking issues, rejection reasons, what failed and why.
     - `pattern`: recurring patterns observed (e.g., "drone footage needed exposure correction").
   - Annotate each chunk with: stage, project_id, format_target, status.
   - Expected output: chunks ready for embedding.

4. **Embed and store in Qdrant.**
   - For each chunk: generate embedding via LM Studio at `localhost:1234/v1`, model `text-embedding-nomic-embed-text-v1.5`.
   - Store in Qdrant collection `hyperedit_knowledge` with metadata:
     ```json
     {
       "stage": "color",
       "project_id": "<id>",
       "format_target": "reel",
       "chunk_type": "failure_mode",
       "content": "...",
       "committed_at": "<timestamp>"
     }
     ```
   - Expected output: chunks stored, confirmed via Qdrant count.

5. **Update RAG index manifest.**
   - Append entry to `state/intel/rag_index_manifest.json`:
     - project_id, stage, committed_at, chunk_count, collection_id.
   - Expected output: manifest updated.

6. **Commit final project record (post-QA only).**
   - After `08-qa-grading.md` completes: commit full project summary.
   - Include: grade card, publish decision, final QC report, all stage QC results.
   - Tag as `project_complete: true` in Qdrant metadata.
   - Expected output: complete project record in RAG index.

7. **Report commit status.**
   - Write commit result to run-ledger: `rag_commits[stage] = { status, chunk_count, committed_at }`.
   - Expected output: run-ledger updated.

## Quality Gates

| Gate | Pass | Warn | Fail |
|------|------|------|------|
| RAG stack healthy | Both services up | One service slow | Any service down |
| Embedding generated | All chunks embedded | — | Any embedding error |
| Chunks stored in Qdrant | Count matches | — | Count mismatch |
| Failure reasons committed | All rejections committed | — | Any rejection missing |
| Provenance metadata present | All fields present | — | Any field missing |

## Outputs

| Artifact | Path |
|----------|------|
| RAG index manifest | `state/intel/rag_index_manifest.json` |
| Run-ledger rag_commits | `state/run-ledger/<project_id>.json → rag_commits` |

## Failure Handling

- **Qdrant unreachable**: Log commit as `pending`. Retry after pipeline completes. Commits are non-blocking — pipeline continues regardless.
- **Embedding model unavailable**: Use lightweight fallback embedding (e.g., sentence-transformers CPU). Document as `warn`.
- **Chunk storage error**: Write commit to local fallback file `state/intel/rag_pending_commits.jsonl`. Retry on next run.
- **Retry policy**: 3 retries with exponential backoff. On persistent failure, stage commit is deferred — pipeline is not blocked.
- **Escalation**: RAG commit failures are non-blocking. Surface as `warn` in final QC report.

## Downstream Dependencies

- Non-blocking — does not gate any pipeline stage.
- Committed records are consumed by: `skills/hyperedit-orchestrator/` (RAG queries during planning), GPU Learning Pipeline Phase 3 (RAG index build).

## Indexed Data Scope

The RAG index (`hyperedit_knowledge`) contains:
- `state/video-analysis-single/*.json` — per-video vision analysis
- `state/audio-analysis/*.json` — audio/DSP analysis results
- `state/final-analysis/*.md` — synthesis reports
- `docs/plans/*.md` — planning documents
- Pipeline stage artifacts (committed by this SOP)

## Skill Cross-Reference

- Skill: `skills/hyperedit-rag-commit/SKILL.md` _(Wave 4 deliverable — not yet created)_
- RAG stack: `rag-local/docker-compose.yml` (OpenWebUI + Qdrant)
- Fast local path: `rag-local/scripts/build_lmstudio_rag.py` + `query_lmstudio_rag.py`
- Setup reference: `docs/plans/2026-02-25-local-rag-openwebui-sop.md`
- Intel patterns for seeding: `state/intel/pattern_analysis.json`, `state/intel/perfect_video_blueprint.md`
- Tutorial corpus: `docs/transcripts/` (33+ indexed transcripts)
