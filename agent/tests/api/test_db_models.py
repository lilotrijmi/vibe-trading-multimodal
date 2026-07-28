from __future__ import annotations

from pathlib import Path

from src.db.models import Conversation, Message, Attachment
from src.db.session import init_db, get_session


def test_init_db_creates_tables(tmp_path: Path) -> None:
    db_path = tmp_path / "test.db"
    init_db(db_path)
    session = get_session()
    try:
        conv = Conversation(title="test")
        session.add(conv)
        session.commit()
        assert conv.id is not None
        assert conv.created_at is not None
    finally:
        session.close()


def test_message_attachment_relationship(tmp_path: Path) -> None:
    db_path = tmp_path / "test.db"
    init_db(db_path)
    session = get_session()
    try:
        conv = Conversation(title="test")
        session.add(conv)
        session.flush()
        msg = Message(conversation_id=conv.id, role="user", content="hi")
        session.add(msg)
        session.flush()
        att = Attachment(
            message_id=msg.id,
            type="image",
            source="test.png",
            mime="image/png",
            size_bytes=100,
            bytes_hash="abc123",
        )
        session.add(att)
        session.commit()
        assert att.id is not None
    finally:
        session.close()
