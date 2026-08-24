"""Build the hybrid retrieval index over the nutrition corpus."""

from __future__ import annotations

import argparse
import json
import pickle
import re
import time
from dataclasses import dataclass

import numpy as np

from nutrivision.config import DATA_DIR, INDEX_DIR

CORPUS_PATH = DATA_DIR / "nutrition" / "corpus.jsonl"
EMBED_MODEL = "BAAI/bge-small-en-v1.5"


@dataclass
class Document:
    doc_id: str
    kind: str
    text: str
    food_class: str
    title: str
    metadata: dict


def load_corpus(path=CORPUS_PATH) -> list[Document]:
    docs = []
    with open(path) as fh:
        for line in fh:
            row = json.loads(line)
            docs.append(
                Document(
                    doc_id=row["doc_id"],
                    kind=row["kind"],
                    text=row["text"],
                    food_class=row["food_class"],
                    title=row["title"],
                    metadata=row.get("metadata", {}),
                )
            )
    return docs


_TOKEN = re.compile(r"[a-z0-9]+")


def tokenize(text: str) -> list[str]:
    """Lowercase alphanumeric tokens, keeping numbers."""
    return _TOKEN.findall(text.lower())


def build(out_dir=INDEX_DIR, model_name: str = EMBED_MODEL) -> dict:
    from rank_bm25 import BM25Okapi
    from sentence_transformers import SentenceTransformer

    out_dir.mkdir(parents=True, exist_ok=True)
    docs = load_corpus()
    started = time.time()

    # Graph facts are indexed alongside the per-dish documents rather than kept in a
    # separate store.
    from .graph import load_graph

    graph_docs = [Document(**d) for d in load_graph().as_documents()]
    docs.extend(graph_docs)

    bm25 = BM25Okapi([tokenize(d.text) for d in docs])

    model = SentenceTransformer(model_name)
    # bge models are trained with a query-side instruction and a bare passage side;
    # embedding passages with the query prefix measurably hurts.
    embeddings = model.encode(
        [d.text for d in docs],
        batch_size=32,
        normalize_embeddings=True,
        show_progress_bar=True,
    ).astype(np.float32)

    np.save(out_dir / "embeddings.npy", embeddings)
    with open(out_dir / "bm25.pkl", "wb") as fh:
        pickle.dump(bm25, fh)
    with open(out_dir / "documents.jsonl", "w") as fh:
        for d in docs:
            fh.write(json.dumps(d.__dict__) + "\n")

    manifest = {
        "documents": len(docs),
        "embed_model": model_name,
        "dim": int(embeddings.shape[1]),
        "kinds": sorted({d.kind for d in docs}),
        "seconds": round(time.time() - started, 2),
    }
    (out_dir / "manifest.json").write_text(json.dumps(manifest, indent=2))
    return manifest


def main() -> None:
    p = argparse.ArgumentParser(description="Build the hybrid retrieval index")
    p.add_argument("--model", default=EMBED_MODEL)
    args = p.parse_args()

    manifest = build(model_name=args.model)
    print(json.dumps(manifest, indent=2))
    print(f"\nwrote {INDEX_DIR}")


if __name__ == "__main__":
    main()
