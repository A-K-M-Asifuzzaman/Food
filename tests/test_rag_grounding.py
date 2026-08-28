from __future__ import annotations

from langchain_core.documents import Document

from nutrivision.rag import ground, pipeline
from nutrivision.rag.retrieve import Hit

SOURCES = (
    "A 140 g slice of pepperoni pizza carries 337 kcal, 12.3 g of protein "
    "and 640 mg of sodium."
)


def hit(text: str, title: str = "Pizza", score: float = 0.9) -> Hit:
    return Hit(
        document=Document(
            page_content=text,
            metadata={"doc_id": "d1", "kind": "nutrients", "title": title, "food_class": "pizza"},
        ),
        score=score,
        rerank_score=score,
    )


def test_numbers_that_appear_in_the_sources_are_supported():
    report = ground.check("A slice has 337 kcal and 640 mg of sodium.", SOURCES)
    assert report.grounded is True
    assert report.unsupported == []


def test_an_invented_number_is_caught():
    report = ground.check("A slice has 950 kcal.", SOURCES)
    assert report.grounded is False
    assert [c.value for c in report.unsupported] == [950.0]


def test_the_report_names_the_nearest_figure_actually_in_the_sources():
    report = ground.check("A slice has 900 kcal.", SOURCES)
    assert report.as_dict()["unsupported"][0]["nearest_in_sources"] is not None


def test_unit_aliases_do_not_count_as_a_new_claim():
    assert ground.check("A slice has 337 calories.", SOURCES).grounded is True
    assert ground.check("It has 12.3 grams of protein.", SOURCES).grounded is True


def test_prose_without_figures_is_trivially_grounded():
    report = ground.check("Pizza is a wheat-based dish baked in an oven.", SOURCES)
    assert report.grounded is True
    assert report.claims == []


def test_a_small_relative_drift_is_tolerated_but_a_large_one_is_not():
    assert ground.check("Around 337.5 kcal.", SOURCES).grounded is True
    assert ground.check("Around 420 kcal.", SOURCES).grounded is False


def test_retrieval_below_the_relevance_floor_is_relaxed_then_refused():
    assert pipeline.after_retrieve({"relevance": -1.0, "floor": 0.0}) == "relax"
    assert pipeline.after_relax({"relevance": -1.0, "floor": 0.0}) == "refuse"


def test_retrieval_above_the_relevance_floor_goes_on_to_generate():
    assert pipeline.after_retrieve({"relevance": 0.8, "floor": 0.2}) == "gate"
    assert pipeline.after_relax({"relevance": 0.8, "floor": 0.2}) == "gate"


def test_a_refusal_is_itself_grounded_and_names_the_knowledge_base():
    refusal = pipeline.refuse({})
    assert refusal["mode"] == "insufficient"
    assert refusal["grounded"] is True
    assert "knowledge base" in refusal["text"]


def test_the_gate_falls_back_to_templates_without_a_key(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    state = {"budget_usd": 1.0}
    assert pipeline.gate(state)["fallback_reason"] == "no api key"
    assert pipeline.after_gate({"fallback_reason": "no api key"}) == "fallback"


def test_the_gate_falls_back_once_the_daily_budget_is_spent(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    monkeypatch.setattr(pipeline, "spend_today", lambda: 2.0)
    assert pipeline.gate({"budget_usd": 1.0})["fallback_reason"] == "budget"


def test_a_generated_answer_that_checks_out_is_kept():
    state = {"text": "A slice has 337 kcal.", "hits": [hit(SOURCES)]}
    verified = pipeline.verify(state)
    assert verified["grounded"] is True
    assert pipeline.after_verify(verified) == "__end__"


def test_a_generated_answer_with_an_invented_number_is_thrown_away():
    state = {"text": "A slice has 1500 kcal.", "hits": [hit(SOURCES)]}
    verified = pipeline.verify(state)
    assert "grounded" not in verified
    assert pipeline.after_verify(verified) == "fallback"

    replacement = pipeline.fallback({**state, **verified})
    assert replacement["mode"] == "template"
    assert replacement["grounded"] is True
    assert "1500" not in replacement["text"]
    assert replacement["grounding"]["rejected"]["unsupported"]


def test_the_template_answer_is_assembled_only_from_retrieved_text():
    state = {"fallback_reason": "no api key", "hits": [hit(SOURCES)]}
    replacement = pipeline.fallback(state)
    assert "337 kcal" in replacement["text"]
    assert ground.check(replacement["text"], SOURCES).grounded is True


def test_a_template_answer_with_nothing_retrieved_claims_nothing():
    replacement = pipeline.fallback({"fallback_reason": "no api key", "hits": []})
    assert replacement["grounded"] is True
    assert ground.extract_quantities(replacement["text"]) == []
