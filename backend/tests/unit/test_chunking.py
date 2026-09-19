"""Unit tests for markdown chunking / normalization."""

from __future__ import annotations

from app.services.chunking import normalize_markdown_whitespace


def test_normalize_preserves_fenced_code_indentation() -> None:
    """Space-collapsing must not destroy indented code blocks.

    A global ``re.sub(r' {1,}', ' ')`` turns nested Python into a
    single flattened string and breaks KB retrieval for code samples.
    """
    source = (
        "# Example\n\n"
        "Use this helper:\n\n"
        "```python\n"
        "def greet(name):\n"
        "    if name:\n"
        "        return f\"hi {name}\"\n"
        "    return \"hi\"\n"
        "```\n"
    )
    normalized = normalize_markdown_whitespace(source)
    assert "    if name:" in normalized
    assert "        return" in normalized
    # Blank-line runs are still collapsed.
    assert "\n\n\n" not in normalized


def test_normalize_collapses_blank_line_runs() -> None:
    text = "para one\n\n\n\npara two\n"
    assert normalize_markdown_whitespace(text) == (
        "para one\n\npara two\n"
    )
