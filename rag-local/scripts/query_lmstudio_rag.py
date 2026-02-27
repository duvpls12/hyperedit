#!/usr/bin/env python3
"""Query local LM Studio embedding index and optionally generate an answer."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

import numpy as np
import requests


DEFAULT_ROOT = Path("/Users/davideby/hyperedit")
DEFAULT_INDEX = Path("/Users/davideby/hyperedit/state/intel/rag_lmstudio")


def parse_env(path: Path) -> dict[str, str]:
    out: dict[str, str] = {}
    if not path.exists():
        return out
    for line in path.read_text(errors="ignore").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        out[k.strip()] = v.strip()
    return out


def lm_embed(host: str, api_key: str, model: str, text: str, timeout: int = 120) -> np.ndarray:
    r = requests.post(
        f"{host.rstrip('/')}/v1/embeddings",
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
        json={"model": model, "input": text},
        timeout=timeout,
    )
    r.raise_for_status()
    vec = r.json()["data"][0]["embedding"]
    return np.asarray(vec, dtype=np.float32)


def lm_chat(host: str, api_key: str, model: str, messages: list[dict], timeout: int = 180) -> str:
    r = requests.post(
        f"{host.rstrip('/')}/v1/chat/completions",
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
        json={"model": model, "messages": messages, "temperature": 0.2, "max_tokens": 1200},
        timeout=timeout,
    )
    r.raise_for_status()
    return r.json()["choices"][0]["message"]["content"]


def resolve_text_model(host: str, api_key: str, preferred: str) -> str:
    """Resolve a model id from /v1/models when preferred is a fuzzy alias."""
    headers = {"Authorization": f"Bearer {api_key}"}
    try:
        r = requests.get(f"{host.rstrip('/')}/v1/models", headers=headers, timeout=30)
        r.raise_for_status()
        ids = [m.get("id", "") for m in r.json().get("data", [])]
    except Exception:
        return preferred

    # Exact match first.
    if preferred in ids:
        return preferred

    # Fuzzy match for gpt-oss alias.
    pref_l = preferred.lower()
    for mid in ids:
        if pref_l in (mid or "").lower():
            return mid
    return preferred


def main() -> None:
    parser = argparse.ArgumentParser(description="Query LM Studio local RAG")
    parser.add_argument("query")
    parser.add_argument("--root", default=str(DEFAULT_ROOT))
    parser.add_argument("--index", default=str(DEFAULT_INDEX))
    parser.add_argument("--top-k", type=int, default=8)
    parser.add_argument("--answer", action="store_true", help="Generate an answer with a text model")
    parser.add_argument("--json", action="store_true", help="Output results as JSON (machine-readable)")
    parser.add_argument("--host", default="")
    parser.add_argument("--api-key", default="")
    parser.add_argument("--embedding-model", default="")
    parser.add_argument("--text-model", default="")
    args = parser.parse_args()

    root = Path(args.root)
    index_dir = Path(args.index)
    docs_path = index_dir / "docs.jsonl"
    vec_path = index_dir / "vectors.npy"
    manifest_path = index_dir / "manifest.json"

    if not docs_path.exists() or not vec_path.exists() or not manifest_path.exists():
        raise SystemExit(f"Missing index artifacts in {index_dir}. Run build_lmstudio_rag.py first.")

    env = parse_env(root / ".env")
    manifest = json.loads(manifest_path.read_text())

    host = args.host or env.get("LM_STUDIO_BASE_URL", "http://127.0.0.1:6759")
    api_key = args.api_key or env.get("LM_STUDIO_API_KEY", "")
    if not api_key:
        raise SystemExit("Missing LM_STUDIO_API_KEY")

    emb_model = args.embedding_model or manifest.get("embedding_model") or "text-embedding-qwen3-embedding-0.6b"
    text_model_pref = args.text_model or os.getenv("TEXT_MODEL") or "gpt-oss-20b"
    text_model = resolve_text_model(host, api_key, text_model_pref)

    docs = [json.loads(line) for line in docs_path.read_text(errors="ignore").splitlines() if line.strip()]
    vecs = np.load(vec_path)
    if len(docs) != len(vecs):
        raise SystemExit(f"docs/vector mismatch: docs={len(docs)} vecs={len(vecs)}")

    q = lm_embed(host, api_key, emb_model, args.query)
    q_norm = q / (np.linalg.norm(q) + 1e-12)
    v_norm = vecs / (np.linalg.norm(vecs, axis=1, keepdims=True) + 1e-12)
    scores = v_norm @ q_norm

    top_idx = np.argsort(scores)[::-1][: args.top_k]

    hits = []
    for rank, idx in enumerate(top_idx, start=1):
        d = docs[int(idx)]
        s = float(scores[int(idx)])
        hits.append({
            "rank": rank,
            "score": round(s, 5),
            "source": d["source"],
            "chunk_index": d["chunk_index"],
            "text": d["text"],
        })

    if args.json:
        print(json.dumps({"results": hits}))
        return

    print("\n=== RETRIEVED CONTEXT ===")
    for h in hits:
        print(f"\n[{h['rank']}] score={h['score']} source={h['source']}#chunk{h['chunk_index']}")
        preview = h["text"][:460].replace("\n", " ")
        print(preview + ("..." if len(h["text"]) > 460 else ""))

    if not args.answer:
        return

    context = "\n\n".join(
        f"SOURCE: {h['source']}#{h['chunk_index']}\n{h['text']}" for h in hits
    )
    messages = [
        {
            "role": "system",
            "content": "You are a precision video-editing knowledge assistant. Use only provided context and cite source paths.",
        },
        {
            "role": "user",
            "content": (
                f"Question: {args.query}\n\n"
                f"Context:\n{context}\n\n"
                "Answer with concise bullets and source citations like [source_path#chunk]."
            ),
        },
    ]

    try:
        ans = lm_chat(host, api_key, text_model, messages)
        used = text_model
    except Exception:
        fallback = "qwen2-audio-7b"
        ans = lm_chat(host, api_key, fallback, messages)
        used = fallback

    print("\n=== ANSWER ===")
    print(f"model: {used}\n")
    print(ans)


if __name__ == "__main__":
    main()
