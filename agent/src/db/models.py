"""SQLAlchemy models for conversations, messages, attachments."""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import (
    Column,
    DateTime,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    pass


class Conversation(Base):
    __tablename__ = "conversations"

    id = Column(Integer, primary_key=True, autoincrement=True)
    title = Column(String, nullable=False, default="New chat")
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(
        DateTime,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )
    summary = Column(Text, nullable=True)
    summarized_until_message_id = Column(Integer, nullable=True)


class Message(Base):
    __tablename__ = "messages"

    id = Column(Integer, primary_key=True, autoincrement=True)
    conversation_id = Column(Integer, nullable=False, index=True)
    role = Column(String, nullable=False)
    content = Column(Text, nullable=False)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))


class Attachment(Base):
    __tablename__ = "attachments"

    id = Column(Integer, primary_key=True, autoincrement=True)
    message_id = Column(Integer, nullable=False, index=True)
    type = Column(String, nullable=False)
    source = Column(String, nullable=False)
    mime = Column(String, nullable=True)
    size_bytes = Column(Integer, nullable=True)
    bytes_hash = Column(String, nullable=True)
    fetched_content = Column(Text, nullable=True)
    vision_description = Column(Text, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    expires_at = Column(DateTime, nullable=True)
