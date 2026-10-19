"""Monthly budget enforce + cost ledger behaviour."""

from __future__ import annotations

import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.models import CostEvent, User
from app.services.cost_tracker import (
    BudgetAction,
    admin_cost_dashboard,
    evaluate_budget,
    record_turn_cost,
)
from tests.integration.helpers import admin_token, assert_ok, bearer


async def _user(db: AsyncSession, *, budget: float | None = 1.0) -> User:
    user = User(
        id=str(uuid.uuid4()),
        email=f"cost-{uuid.uuid4().hex[:8]}@example.com",
        password_hash="x",
        role="user",
        monthly_budget_usd=budget,
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user


@pytest.mark.asyncio
async def test_budget_allows_under_threshold(
    db_session: AsyncSession,
) -> None:
    user = await _user(db_session, budget=1.0)
    status = await evaluate_budget(db_session, user)
    assert status.action is BudgetAction.ALLOW
    assert status.spend_usd == 0.0


@pytest.mark.asyncio
async def test_budget_degrades_then_blocks(
    db_session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("BUDGET_DEGRADE_RATIO", "0.8")
    monkeypatch.setenv("BUDGET_BLOCK_RATIO", "1.0")
    get_settings.cache_clear()
    user = await _user(db_session, budget=1.0)

    # 0.85 of $1 → degrade
    db_session.add(
        CostEvent(
            user_id=user.id,
            model="gpt-4o-mini",
            prompt_tokens=0,
            completion_tokens=0,
            cost_usd=0.85,
        )
    )
    await db_session.commit()
    degraded = await evaluate_budget(db_session, user)
    assert degraded.action is BudgetAction.DEGRADE

    # Push over block
    db_session.add(
        CostEvent(
            user_id=user.id,
            model="gpt-4o-mini",
            prompt_tokens=0,
            completion_tokens=0,
            cost_usd=0.20,
        )
    )
    await db_session.commit()
    blocked = await evaluate_budget(db_session, user)
    assert blocked.action is BudgetAction.BLOCK
    get_settings.cache_clear()


@pytest.mark.asyncio
async def test_record_turn_cost_uses_yaml_pricing(
    db_session: AsyncSession,
) -> None:
    user = await _user(db_session, budget=10.0)
    event = await record_turn_cost(
        db_session,
        user_id=user.id,
        conversation_id=None,
        message_id=None,
        model="gpt-4o-mini",
        prompt_tokens=1000,
        completion_tokens=1000,
    )
    await db_session.commit()
    assert event.cost_usd == pytest.approx(0.00075)


@pytest.mark.asyncio
async def test_admin_cost_dashboard_shape(
    db_session: AsyncSession,
) -> None:
    user = await _user(db_session, budget=10.0)
    await record_turn_cost(
        db_session,
        user_id=user.id,
        conversation_id=str(uuid.uuid4()),
        message_id=None,
        model="gpt-4o-mini",
        prompt_tokens=1000,
        completion_tokens=0,
    )
    await db_session.commit()
    body = await admin_cost_dashboard(db_session, days=7)
    assert body["total_cost_usd"] == pytest.approx(0.00015)
    assert body["avg_cost_per_conversation"] == pytest.approx(0.00015)
    assert len(body["top_users"]) == 1
    assert body["top_users"][0]["email"] == user.email
    assert len(body["daily_trend"]) == 7


@pytest.mark.asyncio
async def test_admin_costs_endpoint(
    client: AsyncClient,
) -> None:
    token = await admin_token(client)
    response = await client.get(
        "/admin/costs",
        headers=bearer(token),
    )
    body = assert_ok(response)
    assert "total_cost_usd" in body
    assert "avg_cost_per_conversation" in body
    assert "top_users" in body
    assert "daily_trend" in body
