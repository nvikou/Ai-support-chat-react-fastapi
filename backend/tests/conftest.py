"""Shared test fixtures; env must exist before app imports Settings."""

import os

os.environ.setdefault("OPENAI_API_KEY", "test-key-not-real")
os.environ.setdefault(
    "DATABASE_URL",
    "postgresql+asyncpg://test:test@localhost:5432/test",
)
