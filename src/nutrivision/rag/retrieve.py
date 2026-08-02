"""Hybrid retrieval: BM25 + dense, fused by RRF, then cross-encoder reranked.

Three stages, each fixing a failure the previous one cannot.

**Fusion over score-mixing.** BM25 returns unbounded relevance scores; cosine
similarity is bounded in [-1, 1]. Any weighted sum of the two needs a
normalisation that is itself a tuned parameter, and it drifts the moment the
corpus changes. Reciprocal Rank Fusion ignores magnitudes and combines *ranks*,
so it has one constant, needs no calibration, and cannot be broken by one
retriever's scores being on a different scale.

**Reranking.** Both first-stage retrievers score a query against a document
independently. A cross-encoder reads them together, which is what catches
"is this high in sodium" retrieving the sodium document for the *wrong dish* -
lexically and semantically near-identical, decisively wrong.

**Dish conditioning, which is specific to this system.** Ordinary RAG starts
from a text query alone. Here the vision model has already named the dish before
a question is asked, so retrieval does not have to guess it.

Conditioning is done by *rewriting the query*, not merely by boosting ranks. Real
questions are asked about a photograph: "how much sodium is in this" contains a
pronoun no retriever can resolve, and against a corpus holding 101 near-identical
sodium documents it will confidently return one about the wrong dish. Naming the
dish in the query fixes all three stages at once - BM25 gains the term, the
bi-encoder gains the topic, and the cross-encoder can finally tell a document
about the right food from one about a different food entirely.

A rank bonus is kept as well, but it cannot do this job alone: reranking sorts
purely by cross-encoder score and would discard any bonus applied before it.
"""

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
            # A rank-space bonus, deliberately not a hard filter. Questions like
            # "which food has the most protein" are answered by the ranking
            # documents, which belong to no single dish; filtering would delete
            # the only documents that can answer them.
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
            # Sorting on the cross-encoder score alone would throw away the dish
            # bonus computed above, so carry it through as a tie-break on the
            # dish rather than letting reranking silently undo the conditioning.
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
