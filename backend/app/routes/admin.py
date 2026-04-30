from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, case
from datetime import datetime, timedelta
from app.database import get_db
from app.models import Conversation, Message

router = APIRouter(prefix="/admin", tags=["admin"])


@router.get("/stats")
async def get_stats(db: AsyncSession = Depends(get_db)):
    total = await db.scalar(select(func.count()).select_from(Conversation))
    escalated = await db.scalar(
        select(func.count()).select_from(Conversation).where(Conversation.escalated == True)
    )
    resolved = await db.scalar(
        select(func.count()).select_from(Conversation).where(Conversation.status == "resolved")
    )
    today = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
    today_count = await db.scalar(
        select(func.count()).select_from(Conversation).where(Conversation.created_at >= today)
    )

    resolution_rate = round((1 - (escalated / total)) * 100, 1) if total else 0

    return {
        "total_conversations": total,
        "escalated": escalated,
        "resolved": resolved,
        "today": today_count,
        "ai_resolution_rate": resolution_rate,
    }


@router.get("/conversations")
async def list_conversations(
    limit: int = 50,
    status: str | None = None,
    db: AsyncSession = Depends(get_db),
):
    query = select(Conversation).order_by(Conversation.updated_at.desc()).limit(limit)
    if status:
        query = query.where(Conversation.status == status)

    result = await db.execute(query)
    conversations = result.scalars().all()

    return [
        {
            "id": c.id,
            "session_id": c.session_id,
            "customer_name": c.customer_name,
            "customer_email": c.customer_email,
            "status": c.status,
            "escalated": c.escalated,
            "escalation_reason": c.escalation_reason,
            "created_at": c.created_at.isoformat(),
            "updated_at": c.updated_at.isoformat(),
        }
        for c in conversations
    ]


@router.get("/conversations/{conversation_id}/messages")
async def get_messages(conversation_id: str, db: AsyncSession = Depends(get_db)):
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
async def resolve_conversation(conversation_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Conversation).where(Conversation.id == conversation_id))
    conv = result.scalar_one_or_none()
    if not conv:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Conversation not found")
    conv.status = "resolved"
    conv.resolved_at = datetime.utcnow()
    await db.commit()
    return {"status": "resolved"}
