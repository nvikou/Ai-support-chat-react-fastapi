import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.deps import get_current_user
from app.models import Conversation, Message, User

router = APIRouter(prefix="/me", tags=["me"])


@router.get("/conversations")
async def list_my_conversations(
    limit: int = 50,
    status: str | None = None,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    query = (
        select(Conversation)
        .where(Conversation.user_id == user.id)
        .order_by(Conversation.updated_at.desc())
        .limit(limit)
    )
    if status:
        query = query.where(Conversation.status == status)

    result = await db.execute(query)
    conversations = result.scalars().all()

    items = []
    for conv in conversations:
        count = await db.scalar(
            select(func.count())
            .select_from(Message)
            .where(Message.conversation_id == conv.id)
        )
        items.append({
            "id": conv.id,
            "session_id": conv.session_id,
            "title": conv.title or "New conversation",
            "status": conv.status,
            "escalated": conv.escalated,
            "message_count": count or 0,
            "created_at": conv.created_at.isoformat(),
            "updated_at": conv.updated_at.isoformat(),
        })
    return items


@router.get("/conversations/{conversation_id}/messages")
async def get_my_messages(
    conversation_id: str,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    result = await db.execute(
        select(Conversation).where(
            Conversation.id == conversation_id,
            Conversation.user_id == user.id,
        )
    )
    conv = result.scalar_one_or_none()
    if not conv:
        raise HTTPException(status_code=404, detail="Conversation not found")

    msg_result = await db.execute(
        select(Message)
        .where(Message.conversation_id == conversation_id)
        .order_by(Message.created_at)
    )
    messages = msg_result.scalars().all()
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


@router.post("/conversations")
async def create_conversation(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    session_id = str(uuid.uuid4())
    conversation = Conversation(
        id=str(uuid.uuid4()),
        session_id=session_id,
        user_id=user.id,
        status="active",
        customer_name=user.full_name,
        customer_email=user.email,
    )
    db.add(conversation)
    await db.commit()
    return {
        "id": conversation.id,
        "session_id": session_id,
        "title": conversation.title,
    }
