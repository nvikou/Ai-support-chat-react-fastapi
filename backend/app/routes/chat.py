import json
import uuid
from datetime import datetime
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.database import get_db
from app.models import Conversation, Message
from app.agent import get_agent

router = APIRouter()


@router.websocket("/ws/chat/{session_id}")
async def chat_websocket(
    websocket: WebSocket,
    session_id: str,
    db: AsyncSession = Depends(get_db),
):
    await websocket.accept()
    agent = get_agent()

    # Load or create conversation
    result = await db.execute(select(Conversation).where(Conversation.session_id == session_id))
    conversation = result.scalar_one_or_none()

    if not conversation:
        conversation = Conversation(
            id=str(uuid.uuid4()),
            session_id=session_id,
            status="active",
        )
        db.add(conversation)
        await db.commit()
        await db.refresh(conversation)

    # Load message history
    msg_result = await db.execute(
        select(Message)
        .where(Message.conversation_id == conversation.id)
        .order_by(Message.created_at)
    )
    history = [
        {"role": m.role, "content": m.content}
        for m in msg_result.scalars().all()
    ]

    # Send welcome message
    await websocket.send_json({
        "type": "connected",
        "conversation_id": conversation.id,
        "escalated": conversation.escalated,
    })

    try:
        while True:
            data = await websocket.receive_json()
            user_message = data.get("message", "").strip()

            if not user_message:
                continue

            # Handle metadata update (name/email)
            if data.get("type") == "identify":
                conversation.customer_name = data.get("name")
                conversation.customer_email = data.get("email")
                await db.commit()
                continue

            # Save user message
            user_msg = Message(
                conversation_id=conversation.id,
                role="user",
                content=user_message,
            )
            db.add(user_msg)
            await db.commit()
            history.append({"role": "user", "content": user_message})

            # Send typing indicator
            await websocket.send_json({"type": "typing"})

            # Get AI response
            response = await agent.answer(user_message, history)

            # Save assistant message
            assistant_msg = Message(
                conversation_id=conversation.id,
                role="assistant",
                content=response["answer"],
                confidence_score=response["confidence"],
                sources=json.dumps(response["sources"]),
            )
            db.add(assistant_msg)
            history.append({"role": "assistant", "content": response["answer"]})

            # Handle escalation
            if response["should_escalate"] and not conversation.escalated:
                conversation.escalated = True
                conversation.escalation_reason = response["escalation_reason"]
                conversation.status = "escalated"

            conversation.updated_at = datetime.utcnow()
            await db.commit()

            # Send response
            await websocket.send_json({
                "type": "message",
                "content": response["answer"],
                "confidence": response["confidence"],
                "sources": response["sources"],
                "escalated": conversation.escalated,
                "escalation_reason": response.get("escalation_reason"),
            })

    except WebSocketDisconnect:
        pass
    except Exception as e:
        await websocket.send_json({"type": "error", "content": str(e)})
