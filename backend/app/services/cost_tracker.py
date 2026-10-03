"""Persist LLM spend and enforce monthly user budgets.

Prometheus counters are process-local and reset on deploy. This ledger
answers durable questions: who spends what, and when to degrade/block.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import Enum
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings, get_settings
from app.models import CostEvent, User
from app.observability.pricing import estimate_cost_usd
from app.timeutils import utc_now

logger = logging.getLogger(__name__)


class BudgetAction(str, Enum):
    """What the chat path must do before calling the LLM."""

    ALLOW = "allow"
    DEGRADE = "degrade"
    BLOCK = "block"


@dataclass(frozen=True)
class BudgetStatus:
    action: BudgetAction
    spend_usd: float
    budget_usd: float
    ratio: float


def month_start(now: datetime | None = None) -> datetime:
    """UTC start of the current calendar month."""
    current = now or utc_now()
    return current.replace(
        day=1,
        hour=0,
        minute=0,
        second=0,
        microsecond=0,
    )


async def effective_budget_usd(
    db: AsyncSession,
    user: User,
    *,
    settings: Settings | None = None,
) -> float:
    """Per-user override, else settings default."""
    cfg = settings or get_settings()
    if user.monthly_budget_usd is not None:
        return float(user.monthly_budget_usd)
    return float(cfg.default_monthly_budget_usd)


async def month_spend_usd(
    db: AsyncSession,
    user_id: str,
    *,
    since: datetime | None = None,
) -> float:
    start = since or month_start()
    total = await db.scalar(
        select(func.coalesce(func.sum(CostEvent.cost_usd), 0.0)).where(
            CostEvent.user_id == user_id,
            CostEvent.created_at >= start,
        )
    )
    return float(total or 0.0)


async def evaluate_budget(
    db: AsyncSession,
    user: User,
    *,
    settings: Settings | None = None,
) -> BudgetStatus:
    """Decide allow / degrade / block from month-to-date spend."""
    cfg = settings or get_settings()
    budget = await effective_budget_usd(db, user, settings=cfg)
    spend = await month_spend_usd(db, user.id)
    if budget <= 0:
        # Misconfigured budget — fail closed rather than free LLM.
        return BudgetStatus(
            action=BudgetAction.BLOCK,
            spend_usd=spend,
            budget_usd=budget,
            ratio=float("inf"),
        )
    ratio = spend / budget
    if ratio >= cfg.budget_block_ratio:
        action = BudgetAction.BLOCK
    elif ratio >= cfg.budget_degrade_ratio:
        action = BudgetAction.DEGRADE
    else:
        action = BudgetAction.ALLOW
    return BudgetStatus(
        action=action,
        spend_usd=spend,
        budget_usd=budget,
        ratio=ratio,
    )


async def record_turn_cost(
    db: AsyncSession,
    *,
    user_id: str,
    conversation_id: str | None,
    message_id: int | None,
    model: str,
    prompt_tokens: int,
    completion_tokens: int,
    purpose: str = "answer_turn",
) -> CostEvent:
    """Persist one assistant-turn cost row."""
    cost = estimate_cost_usd(
        model,
        prompt_tokens=prompt_tokens,
        completion_tokens=completion_tokens,
    )
    event = CostEvent(
        user_id=user_id,
        conversation_id=conversation_id,
        message_id=message_id,
        model=model,
        prompt_tokens=prompt_tokens,
        completion_tokens=completion_tokens,
        cost_usd=cost,
        purpose=purpose,
    )
    db.add(event)
    await db.flush()
    logger.info(
        "cost_recorded",
        extra={
            "event": "cost_recorded",
            "user_id": user_id,
            "conversation_id": conversation_id,
            "model": model,
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "cost_usd": round(cost, 6),
        },
    )
    return event


async def admin_cost_dashboard(
    db: AsyncSession,
    *,
    days: int = 7,
) -> dict[str, Any]:
    """Totals, avg $/conversation, top spenders, daily trend."""
    total_cost = float(
        await db.scalar(
            select(func.coalesce(func.sum(CostEvent.cost_usd), 0.0))
        )
        or 0.0
    )
    conversations_with_cost = int(
        await db.scalar(
            select(func.count(func.distinct(CostEvent.conversation_id))).where(
                CostEvent.conversation_id.is_not(None)
            )
        )
        or 0
    )
    avg_per_conversation = (
        round(total_cost / conversations_with_cost, 6)
        if conversations_with_cost
        else 0.0
    )

    top_rows = await db.execute(
        select(
            CostEvent.user_id,
            User.email,
            func.sum(CostEvent.cost_usd).label("spend"),
        )
        .join(User, User.id == CostEvent.user_id)
        .group_by(CostEvent.user_id, User.email)
        .order_by(func.sum(CostEvent.cost_usd).desc())
        .limit(10)
    )
    top_users = [
        {
            "user_id": row.user_id,
            "email": row.email,
            "cost_usd": round(float(row.spend or 0.0), 6),
        }
        for row in top_rows
    ]

    start = utc_now().replace(
        hour=0,
        minute=0,
        second=0,
        microsecond=0,
    )
    window_start = start - timedelta(days=days - 1)
    day_expr = func.date(CostEvent.created_at)
    trend_rows = await db.execute(
        select(
            day_expr.label("day"),
            func.coalesce(func.sum(CostEvent.cost_usd), 0.0).label("spend"),
        )
        .where(CostEvent.created_at >= window_start)
        .group_by(day_expr)
        .order_by(day_expr)
    )
    by_day = {
        str(row.day): round(float(row.spend or 0.0), 6) for row in trend_rows
    }
    daily_trend: list[dict[str, Any]] = []
    for offset in range(days):
        day = (window_start + timedelta(days=offset)).date()
        key = str(day)
        daily_trend.append(
            {
                "date": key,
                "cost_usd": by_day.get(key, 0.0),
            }
        )

    return {
        "total_cost_usd": round(total_cost, 6),
        "avg_cost_per_conversation": avg_per_conversation,
        "top_users": top_users,
        "daily_trend": daily_trend,
    }
