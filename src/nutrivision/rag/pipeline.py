"""The RAG control flow as a LangGraph state machine.

    START     → retrieve
    retrieve  → gate | relax          is anything relevant enough to answer from?
    relax     → gate | refuse         retry without the dish, then ask again
    gate      → generate | fallback   is there a key, and budget left today?
    generate  → verify
    verify    → END | fallback        is every number in the answer in a source?
    refuse    → END
    fallback  → END

Every branch that used to be an early return in a single function is a node with an
edge, so the path an answer took is inspectable rather than inferred. Run
`python -m nutrivision.rag.pipeline --graph` to print the compiled graph.
"""

from __future__ import annotations

import argparse
import json
import os
import time
from dataclasses import dataclass, field
from functools import lru_cache
from typing import Any, Literal, TypedDict

from langgraph.graph import END, START, StateGraph

from . import ground, load_env
from .generate import (
    DEFAULT_MODEL,
    cost_of,
    format_sources,
    get_chain,
    record_spend,
    spend_today,
    template_answer,
)
from .retrieve import Hit, get_retriever

REFUSAL = (
    "I could not find anything in the nutrition knowledge base that answers that. "
    "It covers the 101 Food-101 dishes and their USDA nutrient profiles."
)


class RagState(TypedDict, total=False):
    """What flows along the edges."""

    question: str
    food_class: str | None
    k: int
    model: str
    reranker: str | None
    budget_usd: float
    hits: list[Hit]
    relevance: float
    floor: float
    relaxed: bool
    text: str
    mode: str
    grounded: bool
    grounding: dict
    usage: dict
    fallback_reason: str
    rejected: dict


@dataclass
class Answer:
    text: str
    citations: list[dict]
    mode: str
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


def _relevance(hits: list[Hit]) -> float:
    return max((h.rerank_score or 0.0) for h in hits) if hits else -99.0


def retrieve(state: RagState) -> dict[str, Any]:
    retriever = get_retriever(state.get("reranker"))
    hits = retriever.search(state["question"], food_class=state["food_class"], k=state["k"])
    return {
        "hits": hits,
        "relevance": _relevance(hits),
        "floor": retriever.reranker.relevance_floor,
        "relaxed": False,
    }


def relax(state: RagState) -> dict[str, Any]:
    """Retry without dish conditioning.

    The question may be general, and the rewritten query can pull retrieval towards
    a dish the user never asked about.
    """
    retriever = get_retriever(state.get("reranker"))
    hits = retriever.search(state["question"], food_class=None, k=state["k"])
    relevance = _relevance(hits)
    if relevance <= state["relevance"]:
        return {"relaxed": True}
    return {"hits": hits, "relevance": relevance, "relaxed": True}


def refuse(state: RagState) -> dict[str, Any]:
    return {"text": REFUSAL, "mode": "insufficient", "grounded": True}


def gate(state: RagState) -> dict[str, Any]:
    """The spend ceiling. Without a key or within budget there is nothing to decide."""
    if not os.environ.get("OPENAI_API_KEY"):
        return {"fallback_reason": "no api key"}
    if spend_today() >= state["budget_usd"]:
        return {"fallback_reason": "budget"}
    return {}


def generate(state: RagState) -> dict[str, Any]:
    message = get_chain(state["model"]).invoke(
        {"context": format_sources(state["hits"]), "question": state["question"]}
    )
    usage = message.usage_metadata or {}
    cost = cost_of(usage)
    record_spend(cost)
    return {
        "text": message.text.strip(),
        "mode": "generated",
        "usage": {
            "model": state["model"],
            "prompt_tokens": usage.get("input_tokens", 0),
            "completion_tokens": usage.get("output_tokens", 0),
            "cost_usd": round(cost, 6),
        },
    }


def verify(state: RagState) -> dict[str, Any]:
    """Every quantity in the answer must appear in the sources it was given."""
    report = ground.check(state["text"], format_sources(state["hits"]))
    if report.grounded:
        return {"grounded": True, "grounding": report.as_dict()}
    return {
        "grounding": report.as_dict(),
        "fallback_reason": "generated answer failed numeric grounding",
        "rejected": report.as_dict(),
    }


def fallback(state: RagState) -> dict[str, Any]:
    """The retrieved record, served verbatim. Correct by construction."""
    grounding: dict[str, Any] = {"reason": state["fallback_reason"]}
    if state.get("rejected"):
        grounding["rejected"] = state["rejected"]
    return {
        "text": template_answer(state["hits"]),
        "mode": "template",
        "grounded": True,
        "grounding": grounding,
    }


def after_retrieve(state: RagState) -> Literal["relax", "gate"]:
    return "gate" if state["relevance"] >= state["floor"] else "relax"


def after_relax(state: RagState) -> Literal["refuse", "gate"]:
    return "gate" if state["relevance"] >= state["floor"] else "refuse"


def after_gate(state: RagState) -> Literal["generate", "fallback"]:
    return "fallback" if state.get("fallback_reason") else "generate"


def after_verify(state: RagState) -> Literal["fallback", "__end__"]:
    return "fallback" if state.get("fallback_reason") else END


@lru_cache(maxsize=1)
def get_pipeline():
    builder = StateGraph(RagState)
    for node in (retrieve, relax, refuse, gate, generate, verify, fallback):
        builder.add_node(node.__name__, node)

    builder.add_edge(START, "retrieve")
    builder.add_conditional_edges("retrieve", after_retrieve)
    builder.add_conditional_edges("relax", after_relax)
    builder.add_conditional_edges("gate", after_gate)
    builder.add_edge("generate", "verify")
    builder.add_conditional_edges("verify", after_verify)
    builder.add_edge("fallback", END)
    builder.add_edge("refuse", END)
    return builder.compile()


def answer(
    question: str,
    food_class: str | None = None,
    k: int = 4,
    model: str | None = None,
    reranker: str | None = None,
    budget_usd: float | None = None,
) -> Answer:
    load_env()
    started = time.time()

    final: RagState = get_pipeline().invoke(
        {
            "question": question,
            "food_class": food_class,
            "k": k,
            "model": model or os.environ.get("OPENAI_MODEL") or DEFAULT_MODEL,
            "reranker": reranker,
            "budget_usd": (
                budget_usd
                if budget_usd is not None
                else float(os.environ.get("OPENAI_DAILY_BUDGET_USD", "1.00"))
            ),
        }
    )

    hits = final.get("hits") or []
    citations = (
        []
        if final["mode"] == "insufficient"
        else [
            {
                "n": i,
                "doc_id": h.doc_id,
                "title": h.title,
                "kind": h.kind,
                "food_class": h.food_class,
            }
            for i, h in enumerate(hits, 1)
        ]
    )
    return Answer(
        text=final["text"],
        citations=citations,
        mode=final["mode"],
        grounded=final["grounded"],
        grounding=final.get("grounding", {}),
        usage=final.get("usage", {}),
        latency_ms=int((time.time() - started) * 1000),
        retrieved=[h.as_dict() for h in hits],
    )


def main() -> None:
    p = argparse.ArgumentParser(description="Ask the grounded nutrition RAG")
    p.add_argument("question", nargs="?")
    p.add_argument("--food-class", default=None)
    p.add_argument("--k", type=int, default=4)
    p.add_argument("--reranker", default=None, help="cohere | cross-encoder")
    p.add_argument("--json", action="store_true")
    p.add_argument("--graph", action="store_true", help="print the graph as mermaid and exit")
    args = p.parse_args()

    if args.graph:
        print(get_pipeline().get_graph().draw_mermaid())
        return
    if not args.question:
        p.error("a question is required unless --graph is given")

    result = answer(
        args.question, food_class=args.food_class, k=args.k, reranker=args.reranker
    )
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
