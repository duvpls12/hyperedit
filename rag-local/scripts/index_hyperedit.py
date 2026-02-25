#!/usr/bin/env python3
import os
import json
import uuid
from pathlib import Path
from typing import List, Dict

import requests
from qdrant_client import QdrantClient
from qdrant_client.http.models import Distance, VectorParams, PointStruct


ROOT = Path(os.getenv("HYPEREDIT_ROOT", "/Users/davideby/hyperedit"))
QDRANT_URL = os.getenv("QDRANT_URL", "http://127.0.0.1:6333")
COLLECTION = os.getenv("QDRANT_COLLECTION", "hyperedit_knowledge")
EMBEDDING_BASE = os.getenv("EMBEDDING_BASE_URL", "http://127.0.0.1:1234/v1")
EMBEDDING_KEY = os.getenv("EMBEDDING_API_KEY", "lm-studio")
EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "text-embedding-nomic-embed-text-v1.5")

TARGETS = [
    ROOT / "state/video-analysis-single",
    ROOT / "state/audio-analysis",
    ROOT / "state/final-analysis",
    ROOT / "docs/plans",
]


def iter_files() -> List[Path]:
    out = []
    for base in TARGETS:
        if not base.exists():
            continue
        for p in base.rglob("*"):
            if not p.is_file():
                continue
            if p.suffix.lower() in {".json", ".md"}:
                out.append(p)
    return out


def chunk_text(text: str, chunk_size: int = 1600, overlap: int = 200) -> List[str]:
    text = text.strip()
    if not text:
        return []
    chunks = []
    i = 0
    while i < len(text):
        j = min(len(text), i + chunk_size)
        chunks.append(text[i:j])
        if j == len(text):
            break
        i = max(j - overlap, i + 1)
    return chunks


def embedding(text: str) -> List[float]:
    resp = requests.post(
        f"{EMBEDDING_BASE}/embeddings",
        headers={"Authorization": f"Bearer {EMBEDDING_KEY}", "Content-Type": "application/json"},
        json={"model": EMBEDDING_MODEL, "input": text},
        timeout=90,
    )
    resp.raise_for_status()
    data = resp.json()
    return data["data"][0]["embedding"]


def build_payload(path: Path, chunk: str, idx: int) -> Dict:
    rel = str(path.relative_to(ROOT)) if str(path).startswith(str(ROOT)) else str(path)
    video_id = path.stem.split("_vision_")[0].split("_audio_")[0]
    return {
        "source": rel,
        "chunk_index": idx,
        "video_id": video_id,
        "ext": path.suffix.lower(),
        "text": chunk,
    }


def main():
    client = QdrantClient(url=QDRANT_URL)

    # Probe first vector size
    vec_probe = embedding("hyperedit embedding probe")
    dim = len(vec_probe)

    if not client.collection_exists(COLLECTION):
        client.create_collection(
            collection_name=COLLECTION,
            vectors_config=VectorParams(size=dim, distance=Distance.COSINE),
        )

    points = []
    files = iter_files()
    for f in files:
        try:
            raw = f.read_text(errors="ignore")
        except Exception:
            continue

        # normalize json for better embedding quality
        if f.suffix.lower() == ".json":
            try:
                obj = json.loads(raw)
                raw = json.dumps(obj, indent=2)
            except Exception:
                pass

        for i, ch in enumerate(chunk_text(raw)):
            try:
                vec = embedding(ch)
            except Exception:
                continue
            payload = build_payload(f, ch, i)
            points.append(
                PointStruct(
                    id=str(uuid.uuid5(uuid.NAMESPACE_URL, payload["source"] + f"::{i}")),
                    vector=vec,
                    payload=payload,
                )
            )

    if points:
        # upsert in batches
        batch = 64
        for i in range(0, len(points), batch):
            client.upsert(collection_name=COLLECTION, points=points[i : i + batch])

    print(json.dumps({"collection": COLLECTION, "files": len(files), "chunks": len(points)}, indent=2))


if __name__ == "__main__":
    main()
