from __future__ import annotations

import json
import logging
import threading
import time
from collections import Counter
from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any

logger = logging.getLogger("app.metrics")

_lock = threading.Lock()
_counters: Counter[str] = Counter()


def reset() -> None:
    with _lock:
        _counters.clear()


def incr(name: str, amount: int = 1) -> None:
    with _lock:
        _counters[name] += amount


def observe_ms(name: str, duration_ms: float) -> None:
    with _lock:
        _counters[f"{name}_count"] += 1
        _counters[f"{name}_total_ms"] += int(duration_ms)


def snapshot() -> dict[str, int]:
    with _lock:
        return dict(_counters)


def log_event(event: str, **fields: Any) -> None:
    payload = {"event": event, **fields}
    logger.info("%s", json.dumps(payload, default=str, sort_keys=True))


@contextmanager
def timed(name: str) -> Iterator[None]:
    started = time.perf_counter()
    try:
        yield
    finally:
        observe_ms(name, (time.perf_counter() - started) * 1000)
