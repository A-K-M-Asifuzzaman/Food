from __future__ import annotations

import json
import time
from collections.abc import Sequence
from functools import lru_cache

from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import Runnable

from nutrivision.config import REPORT_DIR

from .retrieve import Hit

PRICE_IN = 0.40
PRICE_OUT = 1.60

DEFAULT_MODEL = "gpt-4.1-mini"
MAX_TOKENS = 400

SPEND_LOG = REPORT_DIR / "rag_spend.json"

SYSTEM = """You answer questions about food nutrition using ONLY the numbered sources provided.

Rules, in order of importance:
1. Every number you state must appear in the sources. Never estimate, convert, \
scale or infer a figure that is not written there.
2. Cite the source number in square brackets immediately after each fact, like [2].
3. If the sources do not contain the answer, say so plainly. Do not fill the gap \
from general knowledge.
4. Be concise: two or three sentences unless asked for more.
5. Use the units exactly as the sources give them."""

PROMPT = ChatPromptTemplate.from_messages(
    [
        ("system", SYSTEM),
        ("human", "Sources:\n{context}\n\nQuestion: {question}"),
    ]
)


@lru_cache(maxsize=4)
def get_chain(model: str = DEFAULT_MODEL) -> Runnable:
    from langchain_openai import ChatOpenAI

    return PROMPT | ChatOpenAI(model=model, temperature=0, max_tokens=MAX_TOKENS)


def spend_today() -> float:
    try:
        data = json.loads(SPEND_LOG.read_text())
    except (OSError, json.JSONDecodeError):
        return 0.0
    return float(data.get(time.strftime("%Y-%m-%d"), 0.0))


def record_spend(usd: float) -> None:
    try:
        data = json.loads(SPEND_LOG.read_text())
    except (OSError, json.JSONDecodeError):
        data = {}
    today = time.strftime("%Y-%m-%d")
    data[today] = round(data.get(today, 0.0) + usd, 6)
    SPEND_LOG.write_text(json.dumps(data, indent=2, sort_keys=True))


def cost_of(usage: dict) -> float:
    prompt_tokens = usage.get("input_tokens", 0)
    completion_tokens = usage.get("output_tokens", 0)
    return (prompt_tokens * PRICE_IN + completion_tokens * PRICE_OUT) / 1e6


def format_sources(hits: Sequence[Hit]) -> str:
    return "\n\n".join(
        f"[{i}] ({h.kind}, {h.title})\n{h.text}" for i, h in enumerate(hits, 1)
    )


def template_answer(hits: Sequence[Hit]) -> str:
    if not hits:
        return "No matching information was found in the nutrition knowledge base."
    body = " ".join(h.text for h in hits[:2])
    return f"From the USDA-derived record for {hits[0].title}: {body}"
