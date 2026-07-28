from __future__ import annotations

from src.multimodal.abuse_detector import AbuseDetector


def test_detector_records_request() -> None:
    detector = AbuseDetector(window_seconds=60)
    detector.record("user1")
    snapshot = detector.snapshot("user1")
    assert snapshot.request_count == 1


def test_detector_flags_burst() -> None:
    detector = AbuseDetector(window_seconds=60, burst_threshold=5)
    for _ in range(10):
        detector.record("user1")
    snapshot = detector.snapshot("user1")
    assert snapshot.is_burst is True
    assert snapshot.request_count == 10


def test_detector_respects_window() -> None:
    detector = AbuseDetector(window_seconds=1, burst_threshold=5)
    for _ in range(3):
        detector.record("user1")
    snapshot = detector.snapshot("user1")
    assert snapshot.request_count == 3
    import time
    time.sleep(1.1)
    snapshot = detector.snapshot("user1")
    assert snapshot.request_count == 0


def test_detector_isolates_users() -> None:
    detector = AbuseDetector(window_seconds=60, burst_threshold=5)
    for _ in range(10):
        detector.record("user1")
    detector.record("user2")
    s1 = detector.snapshot("user1")
    s2 = detector.snapshot("user2")
    assert s1.is_burst is True
    assert s2.is_burst is False