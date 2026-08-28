from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from backend.app import firebase
from backend.app import store as store_module
from backend.app.store import Store


class FakeBackend:
    name = "fake"

    def __init__(self, fail_times: int = 0) -> None:
        self.rows: dict[str, list[dict]] = {}
        self.fail_times = fail_times
        self.attempts = 0

    def insert(self, collection: str, document: dict) -> None:
        self.attempts += 1
        if self.attempts <= self.fail_times:
            raise ConnectionError("store is not answering")
        self.rows.setdefault(collection, []).append(document)

    def history(self, session: str, limit: int):
        def rows(collection):
            matching = [r for r in self.rows.get(collection, []) if r.get("session") == session]
            return sorted(matching, key=lambda r: r["at"], reverse=True)[:limit]

        return rows("predictions"), rows("questions")

    def scan(self, collection: str, since: datetime):
        return [r for r in self.rows.get(collection, []) if r["at"] >= since]

    def count(self, collection: str, where: dict | None = None):
        return len(self.rows.get(collection, []))

    def delete_session(self, collection: str, session: str) -> int:
        keep = [r for r in self.rows.get(collection, []) if r.get("session") != session]
        removed = len(self.rows.get(collection, [])) - len(keep)
        self.rows[collection] = keep
        return removed


@pytest.fixture
def unconfigured(monkeypatch):
    monkeypatch.setattr(store_module, "MONGO_URI", "")
    monkeypatch.setattr(firebase, "configured", lambda: False)


@pytest.fixture
def configured(monkeypatch):
    monkeypatch.setattr(store_module, "MONGO_URI", "mongodb://example/test")
    monkeypatch.setattr(firebase, "configured", lambda: False)
    monkeypatch.setattr(store_module, "RETRY_SECONDS", 0.0)


def connected(store: Store, backend: FakeBackend) -> Store:
    store.backend = backend
    store.settled.set()
    return store


def a_prediction(store: Store, session: str, title: str = "Pizza") -> None:
    store.record_prediction(
        session=session, email=f"{session}@example.com", food_class="pizza", title=title,
        confidence=0.91, set_size=1, candidates=["pizza"], abstained=False, ms=120,
    )


def drain(store: Store) -> None:
    while not store.queue.empty():
        collection, document = store.queue.get()
        if store.backend is not None:
            store._insert(collection, document)
        store.queue.task_done()


def test_writes_are_dropped_only_when_nothing_is_configured(unconfigured):
    store = Store(start=False)
    assert store.configured is False
    a_prediction(store, "someone")
    assert store.queue.qsize() == 0
    assert store.history("someone")["enabled"] is False


def test_records_made_while_connecting_are_queued_not_lost(configured):
    store = Store(start=False)
    assert store.settled.is_set() is False
    a_prediction(store, "early-bird")
    assert store.queue.qsize() == 1
    assert store.unavailable() == "still connecting to the store"

    backend = FakeBackend()
    connected(store, backend)
    drain(store)
    assert [r["session"] for r in backend.rows["predictions"]] == ["early-bird"]


def test_writes_stop_once_the_connection_is_known_to_have_failed(configured):
    store = Store(start=False)
    store.error = "ServerSelectionTimeoutError: no reachable servers"
    store.settled.set()
    a_prediction(store, "someone")
    assert store.queue.qsize() == 0
    assert store.history("someone")["error"].startswith("ServerSelectionTimeoutError")


def test_a_connection_failure_never_shows_the_caller_the_connection_string(
    configured, monkeypatch
):
    uri = "mongodb+srv://admin:hunter2@cluster0.example.net/foodgenome"

    def explode(_uri):
        raise ConnectionError(f"could not reach {uri}")

    monkeypatch.setattr(store_module, "MongoBackend", explode)
    store = Store(start=False)
    store._connect()

    assert store.error == "ConnectionError"
    surfaces = (store.status(), store.history("someone"), store.analytics(days=1))
    assert not any("hunter2" in repr(surface) for surface in surfaces)


def test_a_transient_insert_failure_is_retried(configured):
    store = connected(Store(start=False), FakeBackend(fail_times=2))
    a_prediction(store, "someone")
    drain(store)
    assert store.failed == 0
    assert len(store.backend.rows["predictions"]) == 1


def test_a_permanent_insert_failure_becomes_a_dead_letter(configured):
    store = connected(Store(start=False), FakeBackend(fail_times=99))
    a_prediction(store, "someone")
    drain(store)
    assert store.failed == 1
    assert store.backend.rows == {}
    assert store.dead_letters[0]["collection"] == "predictions"
    assert store.dead_letters[0]["session"] == "someone"
    assert store.dead_letters[0]["error"] == "ConnectionError"


def test_a_full_queue_counts_drops_rather_than_blocking(configured, monkeypatch):
    monkeypatch.setattr(store_module, "QUEUE_SIZE", 2)
    store = Store(start=False)
    for _ in range(5):
        a_prediction(store, "someone")
    assert store.queue.qsize() == 2
    assert store.dropped == 3


def test_history_returns_only_the_callers_own_rows(configured):
    store = connected(Store(start=False), FakeBackend())
    a_prediction(store, "mine", title="Pizza")
    a_prediction(store, "theirs", title="Ramen")
    store.record_question(
        session="theirs", email=None, question="how much sodium?", food_class="ramen",
        mode="template", grounded=True, citations=2, cost_usd=0.0, ms=40,
    )
    drain(store)

    mine = store.history("mine")
    assert mine["enabled"] is True
    assert [r["title"] for r in mine["predictions"]] == ["Pizza"]
    assert mine["questions"] == []
    assert mine["summary"]["predictions"] == 1


def test_erase_removes_only_the_callers_own_rows(configured):
    store = connected(Store(start=False), FakeBackend())
    a_prediction(store, "mine")
    a_prediction(store, "theirs")
    store.record_feedback(
        session="mine", email=None, food_class="pizza", helpful=False, note="wrong dish"
    )
    drain(store)

    result = store.erase("mine")
    assert result["deleted"] == {"predictions": 1, "questions": 0, "feedback": 1}
    assert [r["session"] for r in store.backend.rows["predictions"]] == ["theirs"]
    assert store.history("mine")["predictions"] == []
    assert store.history("theirs")["summary"]["predictions"] == 1


def test_analytics_reports_what_was_never_written(configured):
    store = connected(Store(start=False), FakeBackend(fail_times=99))
    a_prediction(store, "someone")
    drain(store)
    report = store.analytics(days=7)
    assert report["failed_writes"] == 1
    assert len(report["dead_letters"]) == 1


def test_analytics_rolls_up_by_day_and_by_person(configured):
    store = connected(Store(start=False), FakeBackend())
    a_prediction(store, "mine", title="Pizza")
    a_prediction(store, "mine", title="Pizza")
    a_prediction(store, "theirs", title="Ramen")
    drain(store)

    report = store.analytics(days=7)
    today = datetime.now(UTC).date().isoformat()
    assert report["totals"]["predictions"] == 3
    assert report["totals"]["sessions"] == 2
    assert [d["day"] for d in report["daily"]] == [today]
    assert report["daily"][0]["predictions"] == 3
    people = {p["uid"]: p["predictions"] for p in report["users"]}
    assert people == {"mine": 2, "theirs": 1}


def test_analytics_ignores_rows_older_than_the_window(configured):
    store = connected(Store(start=False), FakeBackend())
    a_prediction(store, "someone")
    drain(store)
    store.backend.rows["predictions"][0]["at"] = datetime.now(UTC) - timedelta(days=30)
    assert store.analytics(days=7)["scanned"]["predictions"] == 0
