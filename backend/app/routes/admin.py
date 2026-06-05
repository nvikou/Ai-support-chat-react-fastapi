from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.database import get_db
from app.deps import require_admin
from app.models import Conversation, Message, User

router = APIRouter(prefix="/admin", tags=["admin"])


@router.get("/stats")
async def get_stats(
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
):
    total = await db.scalar(select(func.count()).select_from(Conversation))
    escalated = await db.scalar(
        select(func.count())
        .select_from(Conversation)
        .where(Conversation.escalated == True)
    )
    resolved = await db.scalar(
        select(func.count())
        .select_from(Conversation)
        .where(Conversation.status == "resolved")
    )
    today = datetime.utcnow().replace(
        hour=0, minute=0, second=0, microsecond=0
    )
    today_count = await db.scalar(
        select(func.count())
        .select_from(Conversation)
        .where(Conversation.created_at >= today)
    )
    user_count = await db.scalar(
        select(func.count()).select_from(User).where(User.role == "user")
    )

    resolution_rate = (
        round((1 - (escalated / total)) * 100, 1) if total else 0
    )

    return {
        "total_conversations": total,
        "escalated": escalated,
        "resolved": resolved,
        "today": today_count,
        "ai_resolution_rate": resolution_rate,
        "total_users": user_count,
    }


@router.get("/conversations")
async def list_conversations(
    limit: int = 50,
    status: str | None = None,
    user_id: str | None = None,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
):
    query = (
        select(Conversation)
        .options(selectinload(Conversation.user))
        .order_by(Conversation.updated_at.desc())
        .limit(limit)
    )
    if status:
        query = query.where(Conversation.status == status)
    if user_id:
        query = query.where(Conversation.user_id == user_id)

    result = await db.execute(query)
    conversations = result.scalars().all()

    return [
        {
            "id": c.id,
            "session_id": c.session_id,
            "title": c.title,
            "customer_name": c.customer_name,
            "customer_email": c.customer_email,
            "user_id": c.user_id,
            "user_name": c.user.full_name if c.user else None,
            "user_email": c.user.email if c.user else None,
            "status": c.status,
            "escalated": c.escalated,
            "escalation_reason": c.escalation_reason,
            "created_at": c.created_at.isoformat(),
            "updated_at": c.updated_at.isoformat(),
        }
        for c in conversations
    ]


@router.get("/conversations/{conversation_id}/messages")
async def get_messages(
    conversation_id: str,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
):
    result = await db.execute(
        select(Message)
        .where(Message.conversation_id == conversation_id)
        .order_by(Message.created_at)
    )
    messages = result.scalars().all()
    return [
        {
            "id": m.id,
            "role": m.role,
            "content": m.content,
            "confidence_score": m.confidence_score,
            "sources": m.sources,
            "created_at": m.created_at.isoformat(),
        }
        for m in messages
    ]


@router.patch("/conversations/{conversation_id}/resolve")
async def resolve_conversation(
    conversation_id: str,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
):
    result = await db.execute(
        select(Conversation).where(Conversation.id == conversation_id)
    )
    conv = result.scalar_one_or_none()
    if not conv:
        raise HTTPException(status_code=404, detail="Conversation not found")
    conv.status = "resolved"
    conv.resolved_at = datetime.utcnow()
    await db.commit()
    return {"status": "resolved"}


@router.get("/users")
async def list_users(
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
):
    result = await db.execute(
        select(User).order_by(User.created_at.desc())
    )
    users = result.scalars().all()

    items = []
    for u in users:
        conv_count = await db.scalar(
            select(func.count())
            .select_from(Conversation)
            .where(Conversation.user_id == u.id)
        )
        items.append({
            "id": u.id,
            "email": u.email,
            "full_name": u.full_name,
            "role": u.role,
            "is_active": u.is_active,
            "conversation_count": conv_count or 0,
            "last_login_at": (
                u.last_login_at.isoformat() if u.last_login_at else None
            ),
            "created_at": u.created_at.isoformat(),
        })
    return items


@router.patch("/users/{user_id}/toggle-active")
async def toggle_user_active(
    user_id: str,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_admin),
):
    if user_id == admin.id:
        raise HTTPException(
            status_code=400,
            detail="Cannot disable your own account",
        )
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    user.is_active = not user.is_active
    await db.commit()
    return {"is_active": user.is_active}
