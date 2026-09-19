"""Markdown normalization and header-aware splitting."""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from langchain.schema import Document


def normalize_markdown_whitespace(text: str) -> str:
    """Collapse blank lines without destroying code indentation.

    A global ``re.sub(r' {1,}', ' ')`` would flatten nested code inside
    fenced blocks and poison retrieval quality for technical docs.
    """
    return re.sub(r"\n[ \t]*\n+", "\n\n", text)


def split_markdown_text(
    markdown_text: str,
    strip_headers: bool = False,
) -> list[Document]:
    """Split Markdown into header-aware LangChain documents."""
    from langchain.schema import Document  # noqa: F401
    from langchain.text_splitter import MarkdownHeaderTextSplitter

    markdown_text = normalize_markdown_whitespace(markdown_text)
    headers_to_split_on = [
        ("#", "Header 1"),
        ("##", "Header 2"),
        ("###", "Header 3"),
    ]
    markdown_splitter = MarkdownHeaderTextSplitter(
        headers_to_split_on=headers_to_split_on,
        strip_headers=strip_headers,
    )
    return markdown_splitter.split_text(markdown_text)
