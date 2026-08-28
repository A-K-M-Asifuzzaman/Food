from __future__ import annotations

import logging
import os
import queue
import threading
import time
from collections import defaultdict, deque
from datetime import UTC, datetime, timedelta

from . import firebase

log = logging.getLogger("foodgenome.store")

MONGO_URI = os.environ.get("MONGODB_URI", "").strip()
DB_NAME = os.environ.get("MONGODB_DB", "foodgenome")

QUEUE_SIZE = 500

SCAN_LIMIT = 5000

WRITE_ATTEMPTS = 3
RETRY_SECONDS = 2.0
DEAD_LETTER_SIZE = 50


class FirestoreBackend:

    name = "firestore"

    def __init__(self) -> None:
        from firebase_admin import firestore

        app = firebase.app()
        if app is None:
            raise RuntimeError(firebase.error() or "firebase admin unavailable")
        self.db = firestore.client(app)
        next(self.db.collection("predictions").limit(1).stream(), None)

    def insert(self, collection: str, document: dict) -> None:
        self.db.collection(collection).add(document)

    def _read(self, collection: str, since: datetime | None = None,
              session: str | None = None, limit: int = SCAN_LIMIT) -> list[dict]:
        query = self.db.collection(collection)
        if session:
            rows = [
                doc.to_dict()
                for doc in query.where("session", "==", session).limit(limit).stream()
            ]
            rows.sort(key=lambda r: r.get("at") or datetime.min.replace(tzinfo=UTC),
                      reverse=True)
            return rows
        if since:
            query = query.where("at", ">=", since)
        return [
            doc.to_dict()
            for doc in query.order_by("at", direction="DESCENDING").limit(limit).stream()
        ]

    def history(self, session: str, limit: int) -> tuple[list[dict], list[dict]]:
        return (
            self._read("predictions", session=session, limit=limit),
            self._read("questions", session=session, limit=limit),
        )

    def scan(self, collection: str, since: datetime) -> list[dict]:
        return self._read(collection, since=since)

    def count(self, collection: str, where: dict | None = None) -> int:
        query = self.db.collection(collection)
        for field, value in (where or {}).items():
            query = query.where(field, "==", value)
        return int(query.count().get()[0][0].value)

    def delete_session(self, collection: str, session: str) -> int:
        removed = 0
        while True:
            docs = list(
                self.db.collection(collection)
                .where("session", "==", session)
                .limit(400)
                .stream()
            )
            if not docs:
                return removed
            batch = self.db.batch()
            for doc in docs:
                batch.delete(doc.reference)
            batch.commit()
            removed += len(docs)


class MongoBackend:
    name = "mongodb"

    def __init__(self, uri: str) -> None:
        from pymongo import ASCENDING, DESCENDING, MongoClient

        client = MongoClient(uri, serverSelectionTimeoutMS=8000, appname="foodgenome")
        client.admin.command("ping")
        self.db = client[DB_NAME]

        self.db.predictions.create_index([("session", ASCENDING), ("at", DESCENDING)])
        self.db.predictions.create_index([("at", DESCENDING)])
        self.db.questions.create_index([("session", ASCENDING), ("at", DESCENDING)])
        self.db.questions.create_index([("at", DESCENDING)])
        self.db.feedback.create_index([("at", DESCENDING)])

    def insert(self, collection: str, document: dict) -> None:
        self.db[collection].insert_one(document)

    def history(self, session: str, limit: int) -> tuple[list[dict], list[dict]]:
        def rows(collection: str) -> list[dict]:
            cursor = (
                self.db[collection]
                .find({"session": session}, {"_id": 0})
                .sort("at", -1)
                .limit(limit)
            )
            return list(cursor)

        return rows("predictions"), rows("questions")

    def scan(self, collection: str, since: datetime) -> list[dict]:
        cursor = (
            self.db[collection]
            .find({"at": {"$gte": since}}, {"_id": 0})
            .sort("at", -1)
            .limit(SCAN_LIMIT)
        )
        return list(cursor)

    def count(self, collection: str, where: dict | None = None) -> int:
        return self.db[collection].count_documents(where or {})

    def delete_session(self, collection: str, session: str) -> int:
        return self.db[collection].delete_many({"session": session}).deleted_count


class Store:
    def __init__(self, *, start: bool = True) -> None:
        self.backend: FirestoreBackend | MongoBackend | None = None
        self.error: str | None = None
        self.queue: queue.Queue[tuple[str, dict]] = queue.Queue(maxsize=QUEUE_SIZE)
        self.dropped = 0
        self.failed = 0
        self.dead_letters: deque[dict] = deque(maxlen=DEAD_LETTER_SIZE)
        self.configured = bool(firebase.configured() or MONGO_URI)
        self.settled = threading.Event()
        if not self.configured:
            self.error = "no MONGODB_URI or FIREBASE_CREDENTIALS configured"
            self.settled.set()
        elif start:
            threading.Thread(target=self._connect, daemon=True).start()
            threading.Thread(target=self._drain, daemon=True).start()

    @property
    def enabled(self) -> bool:
        return self.backend is not None

    @property
    def kind(self) -> str:
        return self.backend.name if self.backend else "none"

    @property
    def accepting(self) -> bool:
        return self.configured and (self.backend is not None or not self.settled.is_set())

    def unavailable(self) -> str | None:
        if self.configured and not self.settled.is_set():
            return "still connecting to the store"
        return self.error

    def status(self) -> dict:
        return {
            "configured": self.configured,
            "backend": self.kind,
            "connected": self.enabled,
            "error": self.error,
            "queued": self.queue.qsize(),
            "dropped_writes": self.dropped,
            "failed_writes": self.failed,
        }

    def _connect(self) -> None:
        try:
            self.backend = (
                FirestoreBackend() if firebase.configured() else MongoBackend(MONGO_URI)
            )
            log.info("store connected: %s", self.backend.name)
        except Exception as exc:
            self.error = type(exc).__name__
            log.warning("store unavailable, running without persistence: %s: %s", self.error, exc)
        finally:
            self.settled.set()

    def _drain(self) -> None:
        self.settled.wait()
        while True:
            collection, document = self.queue.get()
            try:
                if self.backend is None:
                    self.dropped += 1
                else:
                    self._insert(collection, document)
            finally:
                self.queue.task_done()

    def _insert(self, collection: str, document: dict) -> None:
        for attempt in range(1, WRITE_ATTEMPTS + 1):
            try:
                self.backend.insert(collection, document)
                return
            except Exception as exc:
                if attempt == WRITE_ATTEMPTS:
                    self.failed += 1
                    self.dead_letters.append({
                        "collection": collection,
                        "at": document.get("at"),
                        "session": document.get("session"),
                        "error": type(exc).__name__,
                    })
                    log.warning(
                        "insert into %s failed after %d attempts: %s",
                        collection, WRITE_ATTEMPTS, exc,
                    )
                    return
                log.info("insert into %s failed (attempt %d): %s", collection, attempt, exc)
                time.sleep(RETRY_SECONDS * attempt)

    def _write(self, collection: str, document: dict) -> None:
        if not self.accepting:
            return
        try:
            self.queue.put_nowait((collection, document))
        except queue.Full:
            self.dropped += 1


    def record_prediction(self, *, session: str | None, email: str | None,
                          food_class: str, title: str,
                          confidence: float, set_size: int, candidates: list[str],
                          abstained: bool, ms: int) -> None:
        self._write("predictions", {
            "at": datetime.now(UTC),
            "session": session,
            "email": email,
            "food_class": food_class,
            "title": title,
            "confidence": round(confidence, 5),
            "set_size": set_size,
            "candidates": candidates,
            "abstained": abstained,
            "ms": ms,
        })

    def record_question(self, *, session: str | None, email: str | None, question: str,
                        food_class: str | None, mode: str, grounded: bool,
                        citations: int, cost_usd: float, ms: int) -> None:
        self._write("questions", {
            "at": datetime.now(UTC),
            "session": session,
            "email": email,
            "question": question[:200],
            "food_class": food_class,
            "mode": mode,
            "grounded": grounded,
            "citations": citations,
            "cost_usd": round(cost_usd, 6),
            "ms": ms,
        })

    def record_feedback(self, *, session: str | None, email: str | None, food_class: str,
                        helpful: bool, note: str | None) -> None:
        self._write("feedback", {
            "at": datetime.now(UTC),
            "session": session,
            "email": email,
            "food_class": food_class,
            "helpful": helpful,
            "note": (note or "")[:200] or None,
        })


    def history(self, session: str, limit: int = 40) -> dict:
        if not self.enabled:
            return {"enabled": False, "error": self.unavailable()}

        predictions, questions = self.backend.history(session, limit)
        predictions = [_isoformat(r) for r in predictions]
        questions = [_isoformat(r) for r in questions]

        counts: dict[str, int] = defaultdict(int)
        for row in predictions:
            counts[row.get("title", "—")] += 1

        return {
            "enabled": True,
            "predictions": predictions,
            "questions": questions,
            "summary": {
                "predictions": len(predictions),
                "questions": len(questions),
                "abstained": sum(1 for r in predictions if r.get("abstained")),
                "spend_usd": round(sum(r.get("cost_usd", 0.0) for r in questions), 5),
                "most_analysed": sorted(counts.items(), key=lambda kv: -kv[1])[:5],
            },
        }

    def erase(self, session: str) -> dict:
        if not self.enabled:
            return {"enabled": False, "error": self.unavailable()}
        return {
            "enabled": True,
            "deleted": {
                collection: self.backend.delete_session(collection, session)
                for collection in ("predictions", "questions", "feedback")
            },
        }

    def analytics(self, days: int = 14) -> dict:
        if not self.enabled:
            return {"enabled": False, "error": self.unavailable()}

        since = datetime.now(UTC) - timedelta(days=days)
        predictions = [_isoformat(r) for r in self.backend.scan("predictions", since)]
        questions = [_isoformat(r) for r in self.backend.scan("questions", since)]
        feedback = [_isoformat(r) for r in self.backend.scan("feedback", since)]

        by_day: dict[str, dict] = {}
        for row in predictions:
            bucket = by_day.setdefault(row["at"][:10], {
                "day": row["at"][:10], "predictions": 0, "abstained": 0,
                "confidence": 0.0, "set_size": 0, "ms": 0,
            })
            bucket["predictions"] += 1
            bucket["abstained"] += 1 if row.get("abstained") else 0
            bucket["confidence"] += row.get("confidence", 0.0)
            bucket["set_size"] += row.get("set_size", 0)
            bucket["ms"] += row.get("ms", 0)
        daily = []
        for bucket in sorted(by_day.values(), key=lambda b: b["day"]):
            n = bucket["predictions"]
            daily.append({
                "day": bucket["day"],
                "predictions": n,
                "abstained": bucket["abstained"],
                "mean_confidence": round(bucket["confidence"] / n, 4),
                "mean_set_size": round(bucket["set_size"] / n, 3),
                "mean_ms": round(bucket["ms"] / n),
            })

        spend: dict[str, dict] = {}
        for row in questions:
            bucket = spend.setdefault(row["at"][:10], {
                "day": row["at"][:10], "questions": 0, "cost_usd": 0.0,
                "refused": 0, "ungrounded": 0,
            })
            bucket["questions"] += 1
            bucket["cost_usd"] += row.get("cost_usd", 0.0)
            bucket["refused"] += 1 if row.get("mode") == "insufficient" else 0
            bucket["ungrounded"] += 0 if row.get("grounded", True) else 1
        for bucket in spend.values():
            bucket["cost_usd"] = round(bucket["cost_usd"], 6)

        dishes: dict[str, dict] = {}
        for row in predictions:
            bucket = dishes.setdefault(row.get("title", "—"), {
                "title": row.get("title", "—"), "count": 0, "confidence": 0.0, "abstained": 0,
            })
            bucket["count"] += 1
            bucket["confidence"] += row.get("confidence", 0.0)
            bucket["abstained"] += 1 if row.get("abstained") else 0
        top_dishes = sorted(dishes.values(), key=lambda d: -d["count"])[:12]
        for bucket in top_dishes:
            bucket["mean_confidence"] = round(bucket.pop("confidence") / bucket["count"], 4)

        people: dict[str, dict] = {}
        for row in predictions:
            uid = row.get("session") or "anonymous"
            person = people.setdefault(uid, {
                "uid": uid, "email": row.get("email"), "predictions": 0,
                "abstained": 0, "questions": 0, "confidence": 0.0,
                "first_seen": row["at"], "last_seen": row["at"], "dishes": {},
            })
            person["predictions"] += 1
            person["abstained"] += 1 if row.get("abstained") else 0
            person["confidence"] += row.get("confidence", 0.0)
            person["first_seen"] = min(person["first_seen"], row["at"])
            person["last_seen"] = max(person["last_seen"], row["at"])
            title = row.get("title", "—")
            person["dishes"][title] = person["dishes"].get(title, 0) + 1
        for row in questions:
            uid = row.get("session") or "anonymous"
            if uid in people:
                people[uid]["questions"] += 1
        users = []
        for person in sorted(people.values(), key=lambda p: -p["predictions"]):
            n = person["predictions"]
            person["mean_confidence"] = round(person.pop("confidence") / n, 4)
            person["top_dishes"] = sorted(
                person.pop("dishes").items(), key=lambda kv: -kv[1]
            )[:5]
            users.append(person)

        return {
            "enabled": True,
            "backend": self.kind,
            "users": users,
            "days": days,
            "scanned": {
                "predictions": len(predictions),
                "questions": len(questions),
                "limit": SCAN_LIMIT,
            },
            "totals": {
                "predictions": self.backend.count("predictions"),
                "questions": self.backend.count("questions"),
                "feedback": self.backend.count("feedback"),
                "sessions": len({r.get("session") for r in predictions if r.get("session")}),
                "abstained": sum(1 for r in predictions if r.get("abstained")),
                "thumbs_down": sum(1 for r in feedback if not r.get("helpful", True)),
            },
            "daily": daily,
            "spend": sorted(spend.values(), key=lambda b: b["day"]),
            "top_dishes": top_dishes,
            "review_queue": [r for r in predictions if r.get("abstained")][:20],
            "negative_feedback": [r for r in feedback if not r.get("helpful", True)][:20],
            "dropped_writes": self.dropped,
            "failed_writes": self.failed,
            "queued_writes": self.queue.qsize(),
            "dead_letters": list(self.dead_letters),
        }


def _isoformat(row: dict) -> dict:
    at = row.get("at")
    if isinstance(at, datetime):
        row = {**row, "at": at.astimezone(UTC).isoformat()}
    row.pop("_id", None)
    return row


STORE = Store()
