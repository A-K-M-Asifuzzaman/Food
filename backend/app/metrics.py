"""In-process request metrics and a rolling prediction feed.

Deliberately in memory. The alternative discussed in the design was Firestore
plus Prometheus, and that is the right answer for a service with real traffic —
but it is also three accounts and a credentials story for a portfolio deployment
that sleeps after two days idle. Counters that reset when the container restarts
are honest and useful; a dashboard reading an empty external database would be
neither.

Every figure the admin console shows is therefore labelled with the process
start time, so a reader can see the window it covers rather than assuming it is
all-time.
"""

from __future__ import annotations

import threading
import time
from collections import deque
from dataclasses import dataclass, field

# Kept small on purpose: this lives in the same memory as two 300M-parameter
# backbones, and an unbounded history is how a long-lived container runs out.
FEED_SIZE = 40
LATENCY_SAMPLES = 500


@dataclass
class EndpointStats:
    count: int = 0
    errors: int = 0
    latencies_ms: deque[float] = field(default_factory=lambda: deque(maxlen=LATENCY_SAMPLES))

    def percentile(self, p: float) -> float | None:
        if not self.latencies_ms:
            return None
        ordered = sorted(self.latencies_ms)
        # Nearest-rank, which needs no interpolation and is exact for the small
        # sample sizes a demo deployment produces.
        k = max(0, min(len(ordered) - 1, int(round(p / 100 * len(ordered))) - 1))
        return round(ordered[k], 1)


class Metrics:
    def __init__(self) -> None:
        self.started = time.time()
        self.lock = threading.Lock()
        self.endpoints: dict[str, EndpointStats] = {}
        self.predictions: deque[dict] = deque(maxlen=FEED_SIZE)
        self.prediction_count = 0
        self.abstentions = 0
        self.questions = 0
        self.refusals = 0
        self.grounding_failures = 0
        self.openai_cost_usd = 0.0
        self.feedback: deque[dict] = deque(maxlen=FEED_SIZE)
        self.feedback_up = 0
        self.feedback_down = 0

    def record_request(self, path: str, ms: float, ok: bool) -> None:
        with self.lock:
            s = self.endpoints.setdefault(path, EndpointStats())
            s.count += 1
            if not ok:
                s.errors += 1
            s.latencies_ms.append(ms)

    def record_prediction(self, *, title: str, confidence: float, set_size: int,
                          abstained: bool, ms: int) -> None:
        with self.lock:
            self.predictions.appendleft({
                "at": round(time.time()),
                "title": title,
                "confidence": round(confidence, 4),
                "set_size": set_size,
                "abstained": abstained,
                "ms": ms,
            })
            self.prediction_count += 1
            if abstained:
                self.abstentions += 1

    def record_answer(self, *, mode: str, grounded: bool, cost: float) -> None:
        with self.lock:
            self.questions += 1
            if mode == "insufficient":
                self.refusals += 1
            if not grounded:
                self.grounding_failures += 1
            self.openai_cost_usd += cost

    def record_feedback(self, *, food_class: str, helpful: bool, note: str | None) -> None:
        """Thumbs up or down on a prediction.

        Doubles as retraining signal: a thumbs-down on a confident prediction is
        exactly the case worth re-examining, and it is not visible in any
        accuracy metric computed on a labelled split.
        """
        with self.lock:
            self.feedback.appendleft({
                "at": round(time.time()),
                "food_class": food_class,
                "helpful": helpful,
                "note": (note or "")[:200] or None,
            })
            if helpful:
                self.feedback_up += 1
            else:
                self.feedback_down += 1

    @staticmethod
    def _memory() -> dict:
        """Resident set of this process, read from /proc where it exists.

        No psutil dependency for six lines, and the container is Linux, so the
        fallback only matters when running the service on a developer laptop.
        """
        try:
            with open("/proc/self/status") as fh:
                for line in fh:
                    if line.startswith("VmRSS:"):
                        return {"rss_mb": round(int(line.split()[1]) / 1024, 1)}
        except OSError:
            pass
        try:
            import resource
            rss = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
            # Linux reports kilobytes, macOS bytes.
            return {"rss_mb": round(rss / (1024 if rss > 10**7 else 1) / 1024, 1)}
        except Exception:
            return {}

    def snapshot(self) -> dict:
        with self.lock:
            total = sum(s.count for s in self.endpoints.values())
            errors = sum(s.errors for s in self.endpoints.values())
            predictions = list(self.predictions)
            endpoints = {
                path: {
                    "count": s.count,
                    "errors": s.errors,
                    "p50_ms": s.percentile(50),
                    "p95_ms": s.percentile(95),
                    "p99_ms": s.percentile(99),
                }
                for path, s in sorted(self.endpoints.items())
            }
            return {
                "uptime_seconds": round(time.time() - self.started),
                "started_at": round(self.started),
                "requests": total,
                "errors": errors,
                "error_rate": round(errors / total * 100, 2) if total else 0.0,
                "endpoints": endpoints,
                "predictions": {
                    # Completed predictions, not requests to /predict: a GET to
                    # that route is a 405 and belongs in neither figure.
                    "total": self.prediction_count,
                    "abstained": self.abstentions,
                    "recent": predictions,
                },
                "retrieval": {
                    "questions": self.questions,
                    "refusals": self.refusals,
                    "grounding_failures": self.grounding_failures,
                    "openai_cost_usd": round(self.openai_cost_usd, 6),
                },
                "feedback": {
                    "up": self.feedback_up,
                    "down": self.feedback_down,
                    "recent": list(self.feedback),
                },
                "memory": self._memory(),
                "note": "in-process counters; they reset when the container restarts",
            }


METRICS = Metrics()
