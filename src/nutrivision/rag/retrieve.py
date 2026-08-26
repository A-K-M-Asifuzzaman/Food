"""Hybrid retrieval as LangChain retrievers: BM25 + dense, fused by RRF, then reranked."""

from __future__ import annotations

import argparse
import json
import os
from collections.abc import Sequence
from dataclasses import dataclass
from functools import lru_cache
from typing import Any

import numpy as np
from langchain_core.callbacks import CallbackManagerForRetrieverRun, Callbacks
from langchain_core.documents import BaseDocumentCompressor, Document
from langchain_core.retrievers import BaseRetriever
from langchain_core.vectorstores import InMemoryVectorStore
from pydantic import PrivateAttr

from nutrivision.config import INDEX_DIR

from . import load_env
from .index import (
    DOCUMENTS_NAME,
    MANIFEST_NAME,
    VECTORSTORE_NAME,
    get_embeddings,
    load_documents,
    tokenize,
)

CROSS_ENCODER_MODEL = "cross-encoder/ms-marco-MiniLM-L-6-v2"
COHERE_MODEL = "rerank-v3.5"
RRF_K = 60
CANDIDATES = 30
DEFAULT_RERANKER = "cross-encoder"


@dataclass
class Hit:
    document: Document
    score: float
    bm25_rank: int | None = None
    dense_rank: int | None = None
    rerank_score: float | None = None

    @property
    def doc_id(self) -> str:
        return self.document.metadata["doc_id"]

    @property
    def kind(self) -> str:
        return self.document.metadata["kind"]

    @property
    def title(self) -> str:
        return self.document.metadata["title"]

    @property
    def food_class(self) -> str | None:
        return self.document.metadata.get("food_class")

    @property
    def text(self) -> str:
        return self.document.page_content

    def as_dict(self) -> dict:
        return {
            "doc_id": self.doc_id,
            "kind": self.kind,
            "title": self.title,
            "food_class": self.food_class,
            "text": self.text,
            "score": round(self.score, 5),
            "bm25_rank": self.bm25_rank,
            "dense_rank": self.dense_rank,
            "rerank_score": None if self.rerank_score is None else round(self.rerank_score, 4),
        }


class BM25Retriever(BaseRetriever):
    """The lexical half of the hybrid, over the corpus tokenizer that keeps numbers."""

    documents: list[Document]
    k: int = CANDIDATES

    _bm25: Any = PrivateAttr(default=None)

    @property
    def bm25(self):
        if self._bm25 is None:
            from rank_bm25 import BM25Okapi

            self._bm25 = BM25Okapi([tokenize(d.page_content) for d in self.documents])
        return self._bm25

    def _get_relevant_documents(
        self,
        query: str,
        *,
        run_manager: CallbackManagerForRetrieverRun,
        k: int | None = None,
    ) -> list[Document]:
        scores = self.bm25.get_scores(tokenize(query))
        return [self.documents[i] for i in np.argsort(-scores)[: k or self.k]]


class Reranker(BaseDocumentCompressor):
    """A LangChain compressor that also exposes its raw scores.

    The scale of `score` is the reranker's own, and two things downstream are
    expressed in it: `relevance_floor`, below which the pipeline treats the
    evidence as not addressing the question, and `dish_bonus`, the prior for the
    dish the vision model identified. Each backend therefore carries its own.
    """

    model_name: str = ""
    top_n: int = 5
    relevance_floor: float = 0.0
    dish_bonus: float = 0.0

    def score(self, query: str, documents: Sequence[Document]) -> list[float]:
        raise NotImplementedError

    def bonus(self, document: Document, food_class: str | None) -> float:
        if food_class and document.metadata.get("food_class") == food_class:
            return self.dish_bonus
        return 0.0

    def compress_documents(
        self,
        documents: Sequence[Document],
        query: str,
        callbacks: Callbacks | None = None,
        *,
        food_class: str | None = None,
    ) -> Sequence[Document]:
        documents = list(documents)
        scores = self.score(query, documents)
        ranked = sorted(
            zip(documents, scores, strict=True),
            key=lambda pair: -(pair[1] + self.bonus(pair[0], food_class)),
        )
        return [document for document, _ in ranked[: self.top_n]]


class CrossEncoderRerank(Reranker):
    """Local cross-encoder. Emits unbounded logits centred near zero."""

    model_name: str = CROSS_ENCODER_MODEL
    relevance_floor: float = 0.0
    dish_bonus: float = 0.5

    _encoder: Any = PrivateAttr(default=None)

    @property
    def encoder(self):
        if self._encoder is None:
            from sentence_transformers import CrossEncoder

            self._encoder = CrossEncoder(self.model_name)
        return self._encoder

    def score(self, query: str, documents: Sequence[Document]) -> list[float]:
        if not documents:
            return []
        pairs = [(query, d.page_content) for d in documents]
        return [float(s) for s in self.encoder.predict(pairs)]


class CohereRerank(Reranker):
    """Cohere's hosted reranker. Emits relevance in [0, 1], so the floor and the
    dish prior are an order of magnitude smaller than the cross-encoder's.

    A Cohere trial key allows ten calls a minute and answers a 429 otherwise, so
    calls are paced client-side rather than retried into the limit. Set
    `COHERE_REQUESTS_PER_MINUTE` to whatever the key actually permits.
    """

    model_name: str = COHERE_MODEL
    relevance_floor: float = 0.1
    dish_bonus: float = 0.05
    requests_per_minute: float = 10.0

    _client: Any = PrivateAttr(default=None)
    _limiter: Any = PrivateAttr(default=None)

    @property
    def client(self):
        if self._client is None:
            from langchain_cohere import CohereRerank as CohereClient

            load_env()
            self._client = CohereClient(model=self.model_name)
        return self._client

    @property
    def limiter(self):
        if self._limiter is None:
            from langchain_core.rate_limiters import InMemoryRateLimiter

            load_env()
            per_minute = float(
                os.environ.get("COHERE_REQUESTS_PER_MINUTE", self.requests_per_minute)
            )
            self._limiter = InMemoryRateLimiter(
                requests_per_second=per_minute / 60.0,
                check_every_n_seconds=0.25,
                max_bucket_size=1,
            )
        return self._limiter

    def score(self, query: str, documents: Sequence[Document]) -> list[float]:
        if not documents:
            return []
        self.limiter.acquire()
        scores = [0.0] * len(documents)
        for row in self.client.rerank(list(documents), query, top_n=None):
            scores[row["index"]] = float(row["relevance_score"])
        return scores


def get_reranker(name: str | None = None) -> Reranker:
    load_env()
    name = (name or os.environ.get("RAG_RERANKER") or DEFAULT_RERANKER).lower()
    if name in ("cohere", "cohere-rerank"):
        return CohereRerank()
    if name in ("cross-encoder", "cross_encoder", "local"):
        return CrossEncoderRerank()
    raise ValueError(f"Unknown reranker {name!r}: expected 'cohere' or 'cross-encoder'")


class HybridRetriever(BaseRetriever):
    """BM25 and dense retrieval, fused by reciprocal rank fusion and reranked.

    Accepts a `food_class` at query time: the dish the vision model identified is
    named inside the query and given a prior at both fusion and rerank.
    """

    lexical: BM25Retriever
    dense: BaseRetriever
    reranker: Reranker
    documents: list[Document]
    k: int = 5
    candidates: int = CANDIDATES
    rrf_k: int = RRF_K

    def _title_for(self, food_class: str) -> str:
        for d in self.documents:
            if d.metadata.get("food_class") == food_class:
                return d.metadata["title"]
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
        candidates: int | None = None,
    ) -> list[Hit]:
        query = self.contextualise(query, food_class)
        candidates = candidates or self.candidates

        dense_docs = self.dense.invoke(query)[:candidates]
        lexical_docs = self.lexical.invoke(query, k=candidates)

        dense_rank = {d.metadata["doc_id"]: r for r, d in enumerate(dense_docs)}
        bm25_rank = {d.metadata["doc_id"]: r for r, d in enumerate(lexical_docs)}
        by_id = {d.metadata["doc_id"]: d for d in (*dense_docs, *lexical_docs)}

        fused: dict[str, float] = {}
        for ranks in (dense_rank, bm25_rank):
            for doc_id, rank in ranks.items():
                fused[doc_id] = fused.get(doc_id, 0.0) + 1.0 / (self.rrf_k + rank)

        if food_class:
            for doc_id in list(fused):
                if by_id[doc_id].metadata.get("food_class") == food_class:
                    fused[doc_id] += 1.0 / self.rrf_k

        ordered = sorted(fused, key=lambda i: -fused[i])
        hits = [
            Hit(
                document=by_id[doc_id],
                score=fused[doc_id],
                bm25_rank=bm25_rank.get(doc_id),
                dense_rank=dense_rank.get(doc_id),
            )
            for doc_id in ordered[: max(k, 10) if rerank else k]
        ]

        if rerank and hits:
            scores = self.reranker.score(query, [h.document for h in hits])
            for hit, score in zip(hits, scores, strict=True):
                hit.rerank_score = score
            hits.sort(
                key=lambda h: -(h.rerank_score + self.reranker.bonus(h.document, food_class))
            )

        return hits[:k]

    def _get_relevant_documents(
        self,
        query: str,
        *,
        run_manager: CallbackManagerForRetrieverRun,
        food_class: str | None = None,
        k: int | None = None,
        rerank: bool = True,
    ) -> list[Document]:
        hits = self.search(query, food_class=food_class, k=k or self.k, rerank=rerank)
        return [h.document for h in hits]


@lru_cache(maxsize=2)
def get_retriever(reranker: str | None = None, index_dir=INDEX_DIR) -> HybridRetriever:
    manifest = json.loads((index_dir / MANIFEST_NAME).read_text())
    documents = load_documents(index_dir / DOCUMENTS_NAME)
    store = InMemoryVectorStore.load(
        str(index_dir / VECTORSTORE_NAME), get_embeddings(manifest["embed_model"])
    )
    return HybridRetriever(
        lexical=BM25Retriever(documents=documents),
        dense=store.as_retriever(search_kwargs={"k": CANDIDATES}),
        reranker=get_reranker(reranker),
        documents=documents,
    )


def main() -> None:
    p = argparse.ArgumentParser(description="Query the hybrid retriever")
    p.add_argument("query")
    p.add_argument("--food-class", default=None)
    p.add_argument("--k", type=int, default=5)
    p.add_argument("--reranker", default=None, help="cohere | cross-encoder")
    p.add_argument("--no-rerank", action="store_true")
    args = p.parse_args()

    hits = get_retriever(args.reranker).search(
        args.query, food_class=args.food_class, k=args.k, rerank=not args.no_rerank
    )
    for i, h in enumerate(hits, 1):
        marks = []
        if h.bm25_rank is not None:
            marks.append(f"bm25#{h.bm25_rank}")
        if h.dense_rank is not None:
            marks.append(f"dense#{h.dense_rank}")
        if h.rerank_score is not None:
            marks.append(f"rerank {h.rerank_score:+.2f}")
        print(f"{i}. [{h.kind}] {h.title}   ({', '.join(marks)})")
        print(f"   {h.text[:190]}...")


if __name__ == "__main__":
    main()
