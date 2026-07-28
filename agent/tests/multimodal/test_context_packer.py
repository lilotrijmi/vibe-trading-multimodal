from __future__ import annotations

from src.multimodal.context_packer import ContextPacker, AttachmentContext


def test_packer_builds_text_only_context() -> None:
    packer = ContextPacker()
    ctx = packer.build(
        user_text="what is the trend?",
        image_descriptions=[],
        url_contents=[],
    )
    assert ctx.user_text == "what is the trend?"
    assert ctx.image_section == ""
    assert ctx.url_section == ""
    assert ctx.full_prompt.startswith("USER QUESTION: what is the trend?")
    assert "NOT FINANCIAL ADVICE" in ctx.full_prompt


def test_packer_includes_image_descriptions() -> None:
    packer = ContextPacker()
    ctx = packer.build(
        user_text="analyze this chart",
        image_descriptions=[
            AttachmentContext(
                type="image",
                source="chart.png",
                content="uptrend, support at 90",
            )
        ],
        url_contents=[],
    )
    assert "uptrend, support at 90" in ctx.full_prompt
    assert "IMAGE ATTACHMENT" in ctx.full_prompt
    assert "chart.png" in ctx.full_prompt


def test_packer_includes_url_content() -> None:
    packer = ContextPacker()
    ctx = packer.build(
        user_text="summarize this article",
        image_descriptions=[],
        url_contents=[
            AttachmentContext(
                type="url",
                source="https://example.com/article",
                content="article body text",
            )
        ],
    )
    assert "article body text" in ctx.full_prompt
    assert "URL SOURCE" in ctx.full_prompt
    assert "untrusted" in ctx.full_prompt.lower()
