"""Lazy agent accessor so imports stay free of LangChain/FAISS.

Routes and jobs call ``get_agent()`` here. The heavy ``SupportAgent``
module is imported only on first use, which lets offline tests install
an ``OfflineAgent`` via ``override_agent`` without needing OpenAI
packages at collection time.
"""

from __future__ import annotations

from typing import Any

_agent: Any | None = None


def get_agent() -> Any:
    """Return the process-wide support agent (created on first use)."""
    global _agent
    if _agent is None:
        from app.agent import SupportAgent

        _agent = SupportAgent()
    return _agent


def override_agent(agent: Any | None) -> None:
    """Replace or clear the agent (tests only)."""
    global _agent
    _agent = agent
