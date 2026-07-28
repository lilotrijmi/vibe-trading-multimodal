from __future__ import annotations

from unittest.mock import MagicMock

from src.multimodal.summarizer import ConversationSummarizer


def test_should_summarize_when_above_threshold() -> None:
    summarizer = ConversationSummarizer(threshold=50)
    assert summarizer.should_summarize(message_count=51) is True
    assert summarizer.should_summarize(message_count=50) is False
    assert summarizer.should_summarize(message_count=10) is False


def test_summarize_calls_callback() -> None:
    callback = MagicMock(return_value="summary text")
    summarizer = ConversationSummarizer(threshold=50, summarizer_fn=callback)
    messages = [{"role": "user", "content": f"message {i}"} for i in range(100)]
    summary = summarizer.summarize(messages)
    assert summary == "summary text"
    callback.assert_called_once()


def test_summarize_keeps_recent_messages() -> None:
    summarizer = ConversationSummarizer(threshold=50, keep_recent=10)
    messages = [{"role": "user", "content": f"m{i}"} for i in range(100)]
    split = summarizer.split_for_summary(messages)
    assert len(split.recent) == 10
    assert len(split.to_summarize) == 90