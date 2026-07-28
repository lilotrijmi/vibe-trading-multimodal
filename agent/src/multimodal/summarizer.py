"""Auto-summarization for long conversations."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable


@dataclass(frozen=True)
class SplitResult:
    """Split of messages for summarization."""

    to_summarize: list[dict]
    recent: list[dict]


MessageSummarizerFn = Callable[[list[dict]], str]


class ConversationSummarizer:
    """Triggers summarization when conversation exceeds threshold."""

    def __init__(
        self,
        threshold: int = 50,
        keep_recent: int = 10,
        summarizer_fn: MessageSummarizerFn | None = None,
    ) -> None:
        self._threshold = threshold
        self._keep_recent = keep_recent
        self._summarizer_fn = summarizer_fn or self._default_summarizer

    def should_summarize(self, message_count: int) -> bool:
        return message_count > self._threshold

    def split_for_summary(self, messages: list[dict]) -> SplitResult:
        if len(messages) <= self._keep_recent:
            return SplitResult(to_summarize=[], recent=messages)
        split = len(messages) - self._keep_recent
        return SplitResult(
            to_summarize=list(messages[:split]),
            recent=list(messages[split:]),
        )

    def summarize(self, messages: list[dict]) -> str:
        return self._summarizer_fn(messages)

    @staticmethod
    def _default_summarizer(messages: list[dict]) -> str:
        return f"Summary of {len(messages)} messages."