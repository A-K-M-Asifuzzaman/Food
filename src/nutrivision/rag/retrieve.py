"""Hybrid retrieval: BM25 + dense, fused by RRF, then cross-encoder reranked."""

from __future__ import annotations

import argparse
import json
import pickle
from dataclasses import dataclass
from functools import lru_cache

import numpy as np

from nutrivision.config import INDEX_DIR

from .index import Document, tokenize

RERANK_MODEL = "cross-encoder/ms-marco-MiniLM-L-6-v2"
RRF_K = 60
CANDIDATES = 30


@dataclass
class Hit:
    document: Document
    score: float
    bm25_rank: int | None = None
    dense_rank: int | None = None
    rerank_score: float | None = None

    def as_dict(self) -> dict:
        return {
            "doc_id": self.document.doc_id,
            "kind": self.document.kind,
            "title": self.document.title,
            "food_class": self.document.food_class,
            "text": self.document.text,
            "score": round(self.score, 5),
            "bm25_rank": self.bm25_rank,
            "dense_rank": self.dense_rank,
            "rerank_score": None if self.rerank_score is None else round(self.rerank_score, 4),
        }


class Retriever:
    def __init__(self, index_dir=INDEX_DIR):
        self.dir = index_dir
        self.documents = [
            Document(**json.loads(line)) for line in open(index_dir / "documents.jsonl")
        ]
        self.embeddings = np.load(index_dir / "embeddings.npy")
        with open(index_dir / "bm25.pkl", "rb") as fh:
            self.bm25 = pickle.load(fh)
        self.manifest = json.loads((index_dir / "manifest.json").read_text())
        self._encoder = None
        self._reranker = None

    @property
    def encoder(self):
        if self._encoder is None:
            from sentence_transformers import SentenceTransformer

            self._encoder = SentenceTransformer(self.manifest["embed_model"])
        return self._encoder

    @property
    def reranker(self):
        if self._reranker is None:
            from sentence_transformers import CrossEncoder

            self._reranker = CrossEncoder(RERANK_MODEL)
        return self._reranker

    def _dense_ranking(self, query: str) -> np.ndarray:
        # bge expects this instruction on the query side only.
        prefixed = f"Represent this sentence for searching relevant passages: {query}"
        vector = self.encoder.encode(
            [prefixed], normalize_embeddings=True
        ).astype(np.float32)[0]
        return np.argsort(-(self.embeddings @ vector))

    def _bm25_ranking(self, query: str) -> np.ndarray:
        return np.argsort(-self.bm25.get_scores(tokenize(query)))

    def _title_for(self, food_class: str) -> str:
        for d in self.documents:
            if d.food_class == food_class:
                return d.title
        return food_class.replace("_", " ")

    def contextualise(self, query: str, food_class: str | None) -> str:
        """Name the dish inside the query so every stage can use it."""
        if not food_class:
            return query
        return f"{self._title_for(food_class)}: {query}"

    def search(
        self,
        query: str,
        food_class: str | None = None,
        k: int = 5,
        rerank: bool = True,
        candidates: int = CANDIDATES,
    ) -> list[Hit]:
        query = self.contextualise(query, food_class)
        dense_order = self._dense_ranking(query)[:candidates]
        bm25_order = self._bm25_ranking(query)[:candidates]

        dense_rank = {int(i): r for r, i in enumerate(dense_order)}
        bm25_rank = {int(i): r for r, i in enumerate(bm25_order)}

        fused: dict[int, float] = {}
        for ranks in (dense_rank, bm25_rank):
            for idx, rank in ranks.items():
                fused[idx] = fused.get(idx, 0.0) + 1.0 / (RRF_K + rank)

        if food_class:
            # A rank-space bonus, deliberately not a hard filter.
            for idx in list(fused):
                if self.documents[idx].food_class == food_class:
                    fused[idx] += 1.0 / RRF_K

        ordered = sorted(fused, key=lambda i: -fused[i])
        hits = [
            Hit(
                document=self.documents[i],
                score=fused[i],
                bm25_rank=bm25_rank.get(i),
                dense_rank=dense_rank.get(i),
            )
            for i in ordered[: max(k, 10) if rerank else k]
        ]

        if rerank and hits:
            scores = self.reranker.predict([(query, h.document.text) for h in hits])
            for hit, score in zip(hits, scores):
                hit.rerank_score = float(score)
            hits.sort(
                key=lambda h: (
                    -h.rerank_score - (0.5 if food_class and h.document.food_class == food_class else 0.0)
                )
            )

        return hits[:k]


@lru_cache(maxsize=1)
def get_retriever() -> Retriever:
    return Retriever()


def main() -> None:
    p = argparse.ArgumentParser(description="Query the hybrid retriever")
    p.add_argument("query")
    p.add_argument("--food-class", default=None)
    p.add_argument("--k", type=int, default=5)
    p.add_argument("--no-rerank", action="store_true")
    args = p.parse_args()

    hits = get_retriever().search(
        args.query, food_class=args.food_class, k=args.k, rerank=not args.no_rerank
    )
    for i, h in enumerate(hits, 1):
        d = h.document
        marks = []
        if h.bm25_rank is not None:
            marks.append(f"bm25#{h.bm25_rank}")
        if h.dense_rank is not None:
            marks.append(f"dense#{h.dense_rank}")
        if h.rerank_score is not None:
            marks.append(f"rerank {h.rerank_score:+.2f}")
        print(f"{i}. [{d.kind}] {d.title}   ({', '.join(marks)})")
        print(f"   {d.text[:190]}...")


if __name__ == "__main__":
    main()
