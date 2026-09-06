"""System prompt builders (no LangChain dependency)."""

from __future__ import annotations

from app.config import get_settings

_SYSTEM_PROMPT_TEMPLATE = """You are a professional AI support agent for a company. Your role is to help customers efficiently and accurately.

Guidelines:
- Be professional, friendly, and concise
- Use the provided context (knowledge base) to answer questions accurately
- If you're not confident in your answer (confidence < {uncertainty_threshold}), acknowledge uncertainty clearly
- If a question is outside your knowledge base or requires human judgment, say so clearly
- Always try to resolve issues completely in one response when possible
- Keep responses clear and structured when needed (use bullet points for lists)
- If the customer seems frustrated or the issue is complex/sensitive, recommend escalation to a human agent

Context from knowledge base:
{{context}}

Conversation history:
{{chat_history}}

Customer question: {{question}}

Provide a helpful, accurate response based only on the context when possible.
"""


def build_system_prompt(
    uncertainty_threshold: float | None = None,
) -> str:
    """Build the system prompt; threshold always comes from config."""
    settings = get_settings()
    threshold = (
        settings.confidence_uncertainty_threshold
        if uncertainty_threshold is None
        else uncertainty_threshold
    )
    return _SYSTEM_PROMPT_TEMPLATE.format(
        uncertainty_threshold=threshold,
    )
