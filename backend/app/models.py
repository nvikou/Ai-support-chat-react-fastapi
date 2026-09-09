import uuid
from datetime import datetime

from sqlalchemy import (
    String,
    Text,
    DateTime,
    Float,
    Boolean,
    ForeignKey,
    Integer,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.timeutils import utc_now


class User(Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
    )
    email: Mapped[str] = mapped_column(
        String(255), unique=True, index=True
    )
    password_hash: Mapped[str] = mapped_column(String(255))
    full_name: Mapped[str | None] = mapped_column(
        String(255), nullable=True
    )
    role: Mapped[str] = mapped_column(String(20), default="user")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now
    )
    last_login_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    conversations: Mapped[list["Conversation"]] = relationship(
        "Conversation", back_populates="user"
    )
    refresh_tokens: Mapped[list["RefreshToken"]] = relationship(
        "RefreshToken",
        back_populates="user",
        cascade="all, delete-orphan",
    )


class RefreshToken(Base):
    __tablename__ = "refresh_tokens"

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
    )
    user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id"), index=True
    )
    token_hash: Mapped[str] = mapped_column(String(64), unique=True)
    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True)
    )
    revoked: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now
    )

    user: Mapped["User"] = relationship(
        "User", back_populates="refresh_tokens"
    )


class Conversation(Base):
    __tablename__ = "conversations"

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
    )
    session_id: Mapped[str] = mapped_column(String(36), index=True)
    user_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("users.id"),
        nullable=True,
        index=True,
    )
    title: Mapped[str | None] = mapped_column(
        String(255), nullable=True
    )
    customer_email: Mapped[str | None] = mapped_column(
        String(255), nullable=True
    )
    customer_name: Mapped[str | None] = mapped_column(
        String(255), nullable=True
    )
    status: Mapped[str] = mapped_column(
        String(50), default="active"
    )
    escalated: Mapped[bool] = mapped_column(Boolean, default=False)
    escalation_reason: Mapped[str | None] = mapped_column(
        Text, nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        onupdate=utc_now,
    )
    resolved_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    user: Mapped["User | None"] = relationship(
        "User", back_populates="conversations"
    )
    messages: Mapped[list["Message"]] = relationship(
        "Message",
        back_populates="conversation",
        cascade="all, delete-orphan",
    )


class Message(Base):
    __tablename__ = "messages"

    id: Mapped[int] = mapped_column(
        Integer, primary_key=True, autoincrement=True
    )
    conversation_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("conversations.id"),
        index=True,
    )
    role: Mapped[str] = mapped_column(String(20))
    content: Mapped[str] = mapped_column(Text)
    confidence_score: Mapped[float | None] = mapped_column(
        Float, nullable=True
    )
    sources: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now
    )

    conversation: Mapped["Conversation"] = relationship(
        "Conversation", back_populates="messages"
    )


class KnowledgeDocument(Base):
    __tablename__ = "knowledge_documents"

    id: Mapped[int] = mapped_column(
        Integer, primary_key=True, autoincrement=True
    )
    filename: Mapped[str] = mapped_column(String(255))
    content_hash: Mapped[str] = mapped_column(
        String(64), unique=True
    )
    chunk_count: Mapped[int] = mapped_column(Integer, default=0)
    # pending | indexed | failed — set before BackgroundTasks ingest.
    status: Mapped[str] = mapped_column(
        String(20), default="pending", index=True
    )
    error_message: Mapped[str | None] = mapped_column(
        Text, nullable=True
    )
    storage_path: Mapped[str | None] = mapped_column(
        String(512), nullable=True
    )
    uploaded_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now
    )
