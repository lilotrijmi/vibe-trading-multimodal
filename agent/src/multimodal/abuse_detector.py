"""Anomaly detection for abuse monitoring."""

from __future__ import annotations

import time
from collections import defaultdict, deque
from dataclasses import dataclass


@dataclass(frozen=True)
class AbuseSnapshot:
    """Snapshot of activity for a key."""

    request_count: int
    is_burst: bool


class AbuseDetector:
    """Sliding window per-key request counter."""

    def __init__(self, window_seconds: float = 60.0, burst_threshold: int = 100) -> None:
        self._window = window_seconds
        self._threshold = burst_threshold
        self._buckets: dict[str, deque[float]] = defaultdict(deque)

    def record(self, key: str) -> None:
        now = time.time()
        bucket = self._buckets[key]
        bucket.append(now)
        self._evict(bucket, now)

    def snapshot(self, key: str) -> AbuseSnapshot:
        now = time.time()
        bucket = self._buckets[key]
        self._evict(bucket, now)
        count = len(bucket)
        return AbuseSnapshot(
            request_count=count,
            is_burst=count > self._threshold,
        )

    def _evict(self, bucket: deque[float], now: float) -> None:
        cutoff = now - self._window
        while bucket and bucket[0] < cutoff:
            bucket.popleft()