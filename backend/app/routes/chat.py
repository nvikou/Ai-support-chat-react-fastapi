import json
import uuid
from datetime import datetime

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agent import get_agent
from app.database import AsyncSessionLocal
from app.deps import get_user_from_access_token
from app.models import Conversation, Message

router = APIRouter()


def _truncate_title(text: str, max_len: int = 80) -> str:
    cleaned = text.strip()
    if len(cleaned) <= max_len:
        return cleaned
    return cleaned[: max_len - 3] + "..."


@router.websocket("/ws/chat/{session_id}")
async def chat_websocket(
    websocket: WebSocket,
    session_id: str,
    token: str = Query(...),
):
    await websocket.accept()

    async with AsyncSessionLocal() as db:
        user = await get_user_from_access_token(token, db)
        if not user:
            await websocket.send_json({
                "type": "error",
                "content": "Authentication required",
            })
            await websocket.close(code=4401)
            return

        agent = get_agent()

        result = await db.execute(
            select(Conversation).where(Conversation.session_id == session_id)
        )
        conversation = result.scalar_one_or_none()

        if conversation:
            if conversation.user_id and conversation.user_id != user.id:
                await websocket.send_json({
                    "type": "error",
                    "content": "Access denied",
                })
                await websocket.close(code=4403)
                return
            if not conversation.user_id:
                conversation.user_id = user.id
                conversation.customer_email = user.email
                conversation.customer_name = user.full_name
                await db.commit()
        else:
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
            await db.refresh(conversation)

        msg_result = await db.execute(
            select(Message)
            .where(Message.conversation_id == conversation.id)
            .order_by(Message.created_at)
        )
        history = [
            {"role": m.role, "content": m.content}
            for m in msg_result.scalars().all()
        ]

        await websocket.send_json({
            "type": "connected",
            "conversation_id": conversation.id,
            "escalated": conversation.escalated,
            "title": conversation.title,
        })

        try:
            while True:
                data = await websocket.receive_json()
                user_message = data.get("message", "").strip()

                if not user_message:
                    continue

                if data.get("type") == "identify":
                    conversation.customer_name = data.get("name")
                    conversation.customer_email = data.get("email")
                    await db.commit()
                    continue

                if not conversation.title:
                    conversation.title = _truncate_title(user_message)

                user_msg = Message(
                    conversation_id=conversation.id,
                    role="user",
                    content=user_message,
                )
                db.add(user_msg)
                await db.commit()
                history.append({"role": "user", "content": user_message})

                await websocket.send_json({"type": "typing"})

                response = await agent.answer(user_message, history)

                assistant_msg = Message(
                    conversation_id=conversation.id,
                    role="assistant",
                    content=response["answer"],
                    confidence_score=response["confidence"],
                    sources=json.dumps(response["sources"]),
                )
                db.add(assistant_msg)
                history.append({
                    "role": "assistant",
                    "content": response["answer"],
                })

                if response["should_escalate"] and not conversation.escalated:
                    conversation.escalated = True
                    conversation.escalation_reason = response["escalation_reason"]
                    conversation.status = "escalated"

                conversation.updated_at = datetime.utcnow()
                await db.commit()

                await websocket.send_json({
                    "type": "message",
                    "content": response["answer"],
                    "confidence": response["confidence"],
                    "sources": response["sources"],
                    "escalated": conversation.escalated,
                    "escalation_reason": response.get("escalation_reason"),
                    "title": conversation.title,
                })

        except WebSocketDisconnect:
            pass
        except Exception as e:
            await websocket.send_json({"type": "error", "content": str(e)})
