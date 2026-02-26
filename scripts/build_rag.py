#!/usr/bin/env python3
"""
Build local TF-IDF RAG index from all synthesis .md files and intel files.
Saves index to state/intel/rag/ as pickle files.
Query with: python3 scripts/build_rag.py --query "your question here"
"""
import json, sys, pickle, re
from pathlib import Path
from collections import namedtuple

try:
    from sklearn.feature_extraction.text import TfidfVectorizer
    from sklearn.metrics.pairwise import cosine_similarity
    import numpy as np
except ImportError:
    print("Installing sklearn...")
    import subprocess
    subprocess.run([sys.executable, "-m", "pip", "install", "scikit-learn", "numpy", "-q"])
    from sklearn.feature_extraction.text import TfidfVectorizer
    from sklearn.metrics.pairwise import cosine_similarity
    import numpy as np

RAG_DIR = Path("state/intel/rag")
RAG_DIR.mkdir(parents=True, exist_ok=True)

Doc = namedtuple("Doc", ["id", "source", "text", "metadata"])

# ─────────────────────────────────────────────
# 1. Collect all documents
# ─────────────────────────────────────────────
docs = []

# Intel markdown files
intel_dir = Path("state/intel")
for md in intel_dir.glob("*.md"):
    text = md.read_text()
    docs.append(Doc(
        id=md.stem,
        source="intel",
        text=text,
        metadata={"file": str(md), "type": "intel"}
    ))

# Final synthesis .md files
synth_dir = Path("state/final-analysis")
for md in sorted(synth_dir.glob("*_final_synthesis.md")):
    text = md.read_text()
    video_id = md.stem.replace("_final_synthesis", "")
    docs.append(Doc(
        id=video_id,
        source="synthesis",
        text=text,
        metadata={"file": str(md), "type": "synthesis", "video": video_id}
    ))

# Vision pass2 temporal JSONs (add as text)
analysis_dir = Path("state/video-analysis-single")
for jf in sorted(analysis_dir.glob("*_vision_pass2_temporal.json")):
    try:
        data = json.loads(jf.read_text())
        tp = data.get("temporal_post", {})
        summary = tp.get("summary", "")
        shots = tp.get("shots", [])
        shot_types = [s.get("movement_type", "") for s in shots]
        text = f"Video: {jf.stem}\nSummary: {summary}\nShot movements: {', '.join(shot_types)}"
        docs.append(Doc(
            id=jf.stem,
            source="pass2",
            text=text,
            metadata={"file": str(jf), "type": "pass2"}
        ))
    except Exception:
        pass

# Corpus stats as a queryable doc
corpus = json.loads((intel_dir / "corpus_stats.json").read_text())
corpus_text = json.dumps(corpus, indent=2)
docs.append(Doc(
    id="corpus_stats",
    source="intel",
    text=corpus_text,
    metadata={"file": "state/intel/corpus_stats.json", "type": "stats"}
))

print(f"Documents indexed: {len(docs)}")
print(f"  intel files:    {sum(1 for d in docs if d.source == 'intel')}")
print(f"  synthesis:      {sum(1 for d in docs if d.source == 'synthesis')}")
print(f"  pass2 temporal: {sum(1 for d in docs if d.source == 'pass2')}")

# ─────────────────────────────────────────────
# 2. Build TF-IDF index
# ─────────────────────────────────────────────
texts = [d.text for d in docs]
vectorizer = TfidfVectorizer(
    max_features=8000,
    ngram_range=(1, 2),
    stop_words="english",
    min_df=1,
    strip_accents="unicode",
)
tfidf_matrix = vectorizer.fit_transform(texts)
print(f"TF-IDF matrix: {tfidf_matrix.shape}")

# ─────────────────────────────────────────────
# 3. Save index
# ─────────────────────────────────────────────
with open(RAG_DIR / "vectorizer.pkl", "wb") as f:
    pickle.dump(vectorizer, f)
with open(RAG_DIR / "matrix.pkl", "wb") as f:
    pickle.dump(tfidf_matrix, f)
with open(RAG_DIR / "docs.pkl", "wb") as f:
    pickle.dump(docs, f)

print(f"✓ RAG index saved to {RAG_DIR}/")

# ─────────────────────────────────────────────
# 4. Query mode
# ─────────────────────────────────────────────
def query_rag(q, top_k=5):
    q_vec = vectorizer.transform([q])
    sims = cosine_similarity(q_vec, tfidf_matrix).flatten()
    top_idx = sims.argsort()[::-1][:top_k]
    results = []
    for i in top_idx:
        if sims[i] > 0.01:
            d = docs[i]
            snippet = d.text[:600].replace("\n", " ")
            results.append({
                "id": d.id,
                "source": d.source,
                "score": round(float(sims[i]), 4),
                "snippet": snippet,
                "metadata": d.metadata,
            })
    return results


if "--query" in sys.argv:
    idx = sys.argv.index("--query")
    q = " ".join(sys.argv[idx+1:])
    print(f"\n🔍 Query: {q}\n")
    results = query_rag(q)
    for i, r in enumerate(results, 1):
        print(f"--- Result {i} (score={r['score']}) ---")
        print(f"  Source: {r['source']} | ID: {r['id']}")
        print(f"  Snippet: {r['snippet'][:300]}")
        print()
elif __name__ == "__main__" and len(sys.argv) == 1:
    # Run a few test queries
    test_queries = [
        "drone aerial establishing shots",
        "pool water outdoor luxury",
        "hook opening first seconds",
        "music BPM beat sync",
        "living room camera movement pan",
    ]
    print("\n── TEST QUERIES ──")
    for q in test_queries:
        print(f"\n🔍 {q}")
        results = query_rag(q, top_k=3)
        for r in results:
            print(f"  [{r['score']:.3f}] {r['source']}/{r['id']}: {r['snippet'][:120]}")
