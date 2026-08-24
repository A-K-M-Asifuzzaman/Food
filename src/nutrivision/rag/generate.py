"""Grounded answer generation with corrective retrieval and a spend ceiling."""

from __future__ import annotations

import argparse
import json
import os
import pathlib
import time
from dataclasses import dataclass, field

from nutrivision.config import REPORT_DIR

from . import ground
from .retrieve import Hit, get_retriever

# USD per million tokens for gpt-4.1-mini.
PRICE_IN = 0.40
PRICE_OUT = 1.60

SPEND_LOG = REPORT_DIR / "rag_spend.json"

# Below this reranker score the retrieved set is treated as not addressing the question.
RELEVANCE_FLOOR = 0.0

SYSTEM = """You answer questions about food nutrition using ONLY the numbered sources provided.

Rules, in order of importance:
1. Every number you state must appear in the sources. Never estimate, convert, \
scale or infer a figure that is not written there.
2. Cite the source number in square brackets immediately after each fact, like [2].
3. If the sources do not contain the answer, say so plainly. Do not fill the gap \
from general knowledge.
4. Be concise: two or three sentences unless asked for more.
5. Use the units exactly as the sources give them."""


def _load_env() -> None:
    path = pathlib.Path(__file__).resolve().parents[3] / ".env"
    if not path.exists():
        return
    for line in path.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            key, _, value = line.partition("=")
            os.environ.setdefault(key.strip(), value.strip())


@dataclass
class Answer:
    text: str
    citations: list[dict]
    mode: str  # "generated" | "template" | "insufficient"
    grounded: bool
    grounding: dict = field(default_factory=dict)
    usage: dict = field(default_factory=dict)
    latency_ms: int = 0
    retrieved: list[dict] = field(default_factory=list)

    def as_dict(self) -> dict:
        return {
            "answer": self.text,
            "mode": self.mode,
            "grounded": self.grounded,
            "grounding": self.grounding,
            "citations": self.citations,
            "usage": self.usage,
            "latency_ms": self.latency_ms,
            "retrieved": self.retrieved,
        }


def _spend_today() -> float:
    try:
        data = json.loads(SPEND_LOG.read_text())
    except (OSError, json.JSONDecodeError):
        return 0.0
    return float(data.get(time.strftime("%Y-%m-%d"), 0.0))


def _record_spend(usd: float) -> None:
    try:
        data = json.loads(SPEND_LOG.read_text())
    except (OSError, json.JSONDecodeError):
        data = {}
    today = time.strftime("%Y-%m-%d")
    data[today] = round(data.get(today, 0.0) + usd, 6)
    SPEND_LOG.write_text(json.dumps(data, indent=2, sort_keys=True))


def format_sources(hits: list[Hit]) -> str:
    return "\n\n".join(
        f"[{i}] ({h.document.kind}, {h.document.title})\n{h.document.text}"
        for i, h in enumerate(hits, 1)
    )


def template_answer(hits: list[Hit]) -> str:
    """Deterministic fallback assembled from the sources themselves."""
    if not hits:
        return "No matching information was found in the nutrition knowledge base."
    lead = hits[0].document
    body = " ".join(h.document.text for h in hits[:2])
    return f"From the USDA-derived record for {lead.title}: {body}"


def answer(
    question: str,
    food_class: str | None = None,
    k: int = 4,
    model: str | None = None,
    budget_usd: float | None = None,
) -> Answer:
    _load_env()
    started = time.time()
    model = model or os.environ.get("OPENAI_MODEL") or "gpt-4.1-mini"
    budget = budget_usd if budget_usd is not None else float(
        os.environ.get("OPENAI_DAILY_BUDGET_USD", "1.00")
    )

    retriever = get_retriever()
    hits = retriever.search(question, food_class=food_class, k=k)

    # CRAG: is this evidence good enough to answer from?
    best = max((h.rerank_score or 0.0) for h in hits) if hits else -99.0
    if best < RELEVANCE_FLOOR:
        # Retry without dish conditioning; the question may be general, and the
        # rewritten query can pull retrieval towards a dish the user never asked about.
        relaxed = retriever.search(question, food_class=None, k=k)
        relaxed_best = max((h.rerank_score or 0.0) for h in relaxed) if relaxed else -99.0
        if relaxed_best > best:
            hits, best = relaxed, relaxed_best

    retrieved = [h.as_dict() for h in hits]
    citations = [
        {
            "n": i,
            "doc_id": h.document.doc_id,
            "title": h.document.title,
            "kind": h.document.kind,
            "food_class": h.document.food_class,
        }
        for i, h in enumerate(hits, 1)
    ]

    if best < RELEVANCE_FLOOR:
        return Answer(
            text=(
                "I could not find anything in the nutrition knowledge base that answers "
                "that. It covers the 101 Food-101 dishes and their USDA nutrient profiles."
            ),
            citations=[],
            mode="insufficient",
            grounded=True,
            latency_ms=int((time.time() - started) * 1000),
            retrieved=retrieved,
        )

    context = format_sources(hits)

    spent = _spend_today()
    if spent >= budget or not os.environ.get("OPENAI_API_KEY"):
        return Answer(
            text=template_answer(hits),
            citations=citations,
            mode="template",
            grounded=True,
            grounding={"reason": "budget" if spent >= budget else "no api key"},
            latency_ms=int((time.time() - started) * 1000),
            retrieved=retrieved,
        )

    from openai import OpenAI

    client = OpenAI()
    completion = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": SYSTEM},
            {"role": "user", "content": f"Sources:\n{context}\n\nQuestion: {question}"},
        ],
        temperature=0,
        max_tokens=400,
    )
    text = (completion.choices[0].message.content or "").strip()

    usage = completion.usage
    cost = (usage.prompt_tokens * PRICE_IN + usage.completion_tokens * PRICE_OUT) / 1e6
    _record_spend(cost)

    report = ground.check(text, context)
    if not report.grounded:
        # Withheld, not annotated.
        return Answer(
            text=template_answer(hits),
            citations=citations,
            mode="template",
            grounded=True,
            grounding={
                "reason": "generated answer failed numeric grounding",
                "rejected": report.as_dict(),
            },
            usage={
                "model": model,
                "prompt_tokens": usage.prompt_tokens,
                "completion_tokens": usage.completion_tokens,
                "cost_usd": round(cost, 6),
            },
            latency_ms=int((time.time() - started) * 1000),
            retrieved=retrieved,
        )

    return Answer(
        text=text,
        citations=citations,
        mode="generated",
        grounded=True,
        grounding=report.as_dict(),
        usage={
            "model": model,
            "prompt_tokens": usage.prompt_tokens,
            "completion_tokens": usage.completion_tokens,
            "cost_usd": round(cost, 6),
        },
        latency_ms=int((time.time() - started) * 1000),
        retrieved=retrieved,
    )


def main() -> None:
    p = argparse.ArgumentParser(description="Ask the grounded nutrition RAG")
    p.add_argument("question")
    p.add_argument("--food-class", default=None)
    p.add_argument("--k", type=int, default=4)
    p.add_argument("--json", action="store_true")
    args = p.parse_args()

    result = answer(args.question, food_class=args.food_class, k=args.k)
    if args.json:
        print(json.dumps(result.as_dict(), indent=2))
        return

    print(f"[{result.mode}]  grounded={result.grounded}  {result.latency_ms} ms")
    if result.usage:
        print(f"  {result.usage['model']}  ${result.usage['cost_usd']:.6f}")
    print()
    print(result.text)
    if result.citations:
        print("\nsources:")
        for c in result.citations:
            print(f"  [{c['n']}] {c['title']} — {c['kind']}")
    if result.grounding.get("rejected"):
        print("\nrejected generation:", json.dumps(result.grounding["rejected"]))


if __name__ == "__main__":
    main()
