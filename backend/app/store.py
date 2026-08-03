"""Durable storage for predictions, questions and feedback.

The in-process counters in `metrics.py` answer "what is happening now" and lose
everything when the container restarts — which, on a free Space that sleeps
after two days idle, is often. This module answers the other question: what has
happened over time, per dish, per visitor, and at what cost.

Two backends are implemented behind one interface, chosen by whichever
credential is present:

* **Firestore** (`FIREBASE_CREDENTIALS`) — the deployed choice. The project
  already exists, the free tier covers this traffic many times over, and it
  needs no network allowlist, which matters because a Hugging Face Space has no
  stable egress IP to allowlist.
* **MongoDB** (`MONGODB_URI`) — kept because its aggregation pipeline does the
  admin rollups server-side in one round trip, where Firestore has no GROUP BY
  and the same rollups are computed here in Python over a capped window. If the
  analytics ever outgrow that cap, this is the migration path and it is already
  written.

Three properties matter more than the choice:

**It is optional.** With neither credential the whole module is a no-op and
every endpoint still works. A reviewer cloning the repo gets a running service
without signing up for anything.

**Writes never block a response.** The database is a network round-trip away,
sometimes a slow one, and a prediction that already cost seven seconds of
inference should not wait on an insert. Documents go onto a bounded queue and a
daemon thread drains it. If the queue is full or the write fails, the document
is dropped and logged — losing an analytics row is strictly better than failing
a user's request.

**Rows belong to a verified account.** Every document carries the Firebase uid
from the caller's ID token, not an id the request asked to be filed under. That
is what lets `/history` return your predictions and nobody else's: the uid comes
from the signature, so there is no value a caller can send to read another
account's rows. Stored alongside it is the email, which is what the admin
console shows.

Nothing in the browser talks to the database directly. The security rules in
`firestore.rules` deny all client access; every read goes through the API, where
`/history` is scoped to the caller and `/analytics` is checked against the admin
list.
"""

from __future__ import annotations

import json
import logging
import os
import queue
import threading
from collections import defaultdict
from datetime import datetime, timedelta, timezone

log = logging.getLogger("foodgenome.store")

MONGO_URI = os.environ.get("MONGODB_URI", "").strip()
FIREBASE_CREDENTIALS = os.environ.get("FIREBASE_CREDENTIALS", "").strip()
DB_NAME = os.environ.get("MONGODB_DB", "foodgenome")

# Bounded: if the database is unreachable the queue must not grow until the
# container is killed for memory. 500 pending documents is far more than this
# service can generate while a single write is in flight.
QUEUE_SIZE = 500

# Firestore has no aggregation pipeline, so analytics read documents and group
# them here. The cap is what keeps that honest: past it, the numbers would
# quietly describe a subset while looking like a total, so the payload says how
# many rows it actually read.
SCAN_LIMIT = 5000


# ── backends ────────────────────────────────────────────────────────────


class FirestoreBackend:
    """Google Firestore, via the Admin SDK.

    The admin SDK bypasses security rules, which is why the rules can deny every
    client operation outright. The only path to this data is through this
    process.
    """

    name = "firestore"

    def __init__(self, credentials_json: str) -> None:
        import firebase_admin
        from firebase_admin import credentials, firestore

        info = json.loads(credentials_json)
        app = firebase_admin.initialize_app(credentials.Certificate(info))
        self.db = firestore.client(app)
        # A cheap round-trip, so a bad key fails at startup rather than on the
        # first prediction.
        next(self.db.collection("predictions").limit(1).stream(), None)

    def insert(self, collection: str, document: dict) -> None:
        self.db.collection(collection).add(document)

    def _read(self, collection: str, since: datetime | None = None,
              session: str | None = None, limit: int = SCAN_LIMIT) -> list[dict]:
        """One filtered read.

        Firestore will not combine an equality filter with an order_by on a
        different field without a composite index, and a project that has to be
        told to build three indexes before its history page works is a project
        that does not work on a fresh clone. So the session query is sorted
        here instead: it is capped at a hundred rows by the endpoint, and
        sorting a hundred dictionaries costs nothing next to the round trip
        that fetched them.

        The time-range scan keeps its server-side sort — that one is a single
        field, so it needs no index and can be limited before transfer.
        """
        query = self.db.collection(collection)
        if session:
            rows = [
                doc.to_dict()
                for doc in query.where("session", "==", session).limit(limit).stream()
            ]
            rows.sort(key=lambda r: r.get("at") or datetime.min.replace(tzinfo=timezone.utc),
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
        # count() is a server-side aggregation and does not read the documents.
        return int(query.count().get()[0][0].value)

    def delete_session(self, collection: str, session: str) -> int:
        # Firestore has no "delete by query"; the documents have to be walked.
        # Batched at 400, under the 500-operation limit on a write batch.
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

        # The two read paths that exist: a visitor's own history, and day buckets.
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


# ── the store ───────────────────────────────────────────────────────────


class Store:
    def __init__(self) -> None:
        self.backend: FirestoreBackend | MongoBackend | None = None
        self.error: str | None = None
        self.queue: queue.Queue[tuple[str, dict]] = queue.Queue(maxsize=QUEUE_SIZE)
        self.dropped = 0
        if FIREBASE_CREDENTIALS or MONGO_URI:
            threading.Thread(target=self._connect, daemon=True).start()
        else:
            self.error = "no MONGODB_URI or FIREBASE_CREDENTIALS configured"

    @property
    def enabled(self) -> bool:
        return self.backend is not None

    @property
    def kind(self) -> str:
        return self.backend.name if self.backend else "none"

    def _connect(self) -> None:
        try:
            self.backend = (
                FirestoreBackend(FIREBASE_CREDENTIALS)
                if FIREBASE_CREDENTIALS
                else MongoBackend(MONGO_URI)
            )
            log.info("store connected: %s", self.backend.name)
            threading.Thread(target=self._drain, daemon=True).start()
        except Exception as exc:  # noqa: BLE001 — any failure means "run without it"
            # First line only. Google's PermissionDenied carries forty lines of
            # protobuf metadata, and pasting that into a dashboard panel tells a
            # reader nothing the first sentence did not.
            self.error = f"{type(exc).__name__}: {str(exc).splitlines()[0][:200]}"
            log.warning("store unavailable, running without persistence: %s", self.error)

    def _drain(self) -> None:
        while True:
            collection, document = self.queue.get()
            try:
                self.backend.insert(collection, document)
            except Exception as exc:  # noqa: BLE001
                log.warning("insert failed (%s): %s", collection, exc)
            finally:
                self.queue.task_done()

    def _write(self, collection: str, document: dict) -> None:
        if not self.enabled:
            return
        try:
            self.queue.put_nowait((collection, document))
        except queue.Full:
            self.dropped += 1

    # ── writes ──────────────────────────────────────────────────────────

    def record_prediction(self, *, session: str | None, email: str | None,
                          food_class: str, title: str,
                          confidence: float, set_size: int, candidates: list[str],
                          abstained: bool, ms: int) -> None:
        self._write("predictions", {
            "at": datetime.now(timezone.utc),
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
            "at": datetime.now(timezone.utc),
            "session": session,
            "email": email,
            # Truncated: the analytics need the shape of what people ask, not a
            # verbatim log of it.
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
            "at": datetime.now(timezone.utc),
            "session": session,
            "email": email,
            "food_class": food_class,
            "helpful": helpful,
            "note": (note or "")[:200] or None,
        })

    # ── reads ───────────────────────────────────────────────────────────

    def history(self, session: str, limit: int = 40) -> dict:
        """One visitor's own record, keyed by the id their browser generated."""
        if not self.enabled:
            return {"enabled": False, "error": self.error}

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
        """Delete everything belonging to one account.

        Offered because the history page promises it. A record a person cannot
        remove is not a record they consented to keep, and "contact us to
        delete your data" is not a delete button.
        """
        if not self.enabled:
            return {"enabled": False, "error": self.error}
        return {
            "enabled": True,
            "deleted": {
                collection: self.backend.delete_session(collection, session)
                for collection in ("predictions", "questions", "feedback")
            },
        }

    def analytics(self, days: int = 14) -> dict:
        """Aggregates for the admin console: volume, dishes, cost, reliability.

        Distinct from /stats, which reports the current container and is empty
        after every restart. These survive.
        """
        if not self.enabled:
            return {"enabled": False, "error": self.error}

        since = datetime.now(timezone.utc) - timedelta(days=days)
        predictions = [_isoformat(r) for r in self.backend.scan("predictions", since)]
        questions = [_isoformat(r) for r in self.backend.scan("questions", since)]
        feedback = [_isoformat(r) for r in self.backend.scan("feedback", since)]

        # Day buckets for volume and reliability.
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

        # Spend per day, which is the number that decides whether the generator
        # stays on the hosted model or falls back to templates.
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

        # Per account. This is the admin answer to "who is using it and what
        # are they photographing" — one row per signed-in user rather than one
        # per request, because thirty predictions from one person is a
        # different fact from thirty people trying it once.
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
            # The review queue: what the model declined, and what a person said
            # it got wrong. Neither is visible in any metric computed on a
            # labelled split.
            "review_queue": [r for r in predictions if r.get("abstained")][:20],
            "negative_feedback": [r for r in feedback if not r.get("helpful", True)][:20],
            "dropped_writes": self.dropped,
        }


def _isoformat(row: dict) -> dict:
    """Datetimes out of either driver become ISO strings for JSON."""
    at = row.get("at")
    if isinstance(at, datetime):
        row = {**row, "at": at.astimezone(timezone.utc).isoformat()}
    row.pop("_id", None)
    return row


STORE = Store()
