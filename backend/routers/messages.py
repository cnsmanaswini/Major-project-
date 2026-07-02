"""
Messages Router — Real-time WebSocket chat
GET  /api/messages/conversations     → list conversations
GET  /api/messages/thread/{user_id}  → get message thread
POST /api/messages                   → send message (REST fallback)
WS   /api/messages/ws/{user_id}      → WebSocket live chat
"""

from fastapi import APIRouter, Depends, HTTPException, WebSocket, WebSocketDisconnect
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, or_, and_
from typing import Dict, List
from datetime import datetime
import json

from models.database import get_db
from models.models import Message, User, EmotionLog, Notification
from schemas.schemas import MessageCreate, MessageOut
from routers.auth import get_current_user
from ai.pipeline.analyzer import analyze_text

router = APIRouter()


# ── WebSocket Connection Manager ──────────────────────────────

class ConnectionManager:
    def __init__(self):
        # user_id → list of websockets
        self.active: Dict[int, List[WebSocket]] = {}

    async def connect(self, user_id: int, websocket: WebSocket):
        await websocket.accept()
        if user_id not in self.active:
            self.active[user_id] = []
        self.active[user_id].append(websocket)

    def disconnect(self, user_id: int, websocket: WebSocket):
        if user_id in self.active:
            self.active[user_id].remove(websocket)
            if not self.active[user_id]:
                del self.active[user_id]

    async def send_to_user(self, user_id: int, data: dict):
        """Send message to a specific user if they are online."""
        if user_id in self.active:
            message_str = json.dumps(data)
            for ws in self.active[user_id]:
                try:
                    await ws.send_text(message_str)
                except Exception:
                    pass

    def is_online(self, user_id: int) -> bool:
        return user_id in self.active and len(self.active[user_id]) > 0


manager = ConnectionManager()


# ── WebSocket Endpoint ────────────────────────────────────────

@router.websocket("/ws/{user_id}")
async def websocket_chat(
    websocket: WebSocket,
    user_id: int,
    db: AsyncSession = Depends(get_db),
):
    """
    Real-time WebSocket chat endpoint.
    Messages are analyzed by AI pipeline on the fly.
    """
    await manager.connect(user_id, websocket)
    try:
        while True:
            # Receive message from client
            raw = await websocket.receive_text()
            data = json.loads(raw)

            receiver_id = data.get("receiver_id")
            content = data.get("content", "").strip()

            if not content or not receiver_id:
                continue

            # Verify users exist
            sender = await db.get(User, user_id)
            receiver = await db.get(User, receiver_id)
            if not sender or not receiver:
                continue

            # Run AI pipeline silently
            pipeline = analyze_text(content)

            # Save message
            msg = Message(
                sender_id=user_id,
                receiver_id=receiver_id,
                content=content,
                sentiment=pipeline.sentiment,
                emotion=pipeline.emotion,
                risk_score=pipeline.risk_score,
            )
            db.add(msg)

            # Log emotion
            db.add(EmotionLog(
                user_id=user_id,
                sentiment_score=pipeline.sentiment_score,
                emotion=pipeline.emotion,
                emotion_score=pipeline.emotion_score,
                risk_score=pipeline.risk_score,
                source="message",
            ))

            await db.commit()
            await db.refresh(msg)

            # Build response payload
            payload = {
                "id": msg.id,
                "sender_id": user_id,
                "receiver_id": receiver_id,
                "content": content,
                "created_at": msg.created_at.isoformat(),
                "sentiment": pipeline.sentiment,
                "emotion": pipeline.emotion,
                "risk_score": pipeline.risk_score,
                "sender": {
                    "username": sender.username,
                    "avatar_url": sender.avatar_url,
                    "display_name": sender.display_name,
                },
            }

            # Send to sender (confirmation)
            await manager.send_to_user(user_id, {
                "type": "message_sent",
                **payload,
            })

            # Send to receiver (if online)
            await manager.send_to_user(receiver_id, {
                "type": "new_message",
                **payload,
            })

    except WebSocketDisconnect:
        manager.disconnect(user_id, websocket)


# ── REST Endpoints ────────────────────────────────────────────

@router.post("", response_model=MessageOut, status_code=201)
async def send_message(
    body: MessageCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """REST fallback for sending messages."""
    receiver = await db.get(User, body.receiver_id)
    if not receiver:
        raise HTTPException(status_code=404, detail="User not found")

    pipeline = analyze_text(body.content)

    msg = Message(
        sender_id=current_user.id,
        receiver_id=body.receiver_id,
        content=body.content,
        sentiment=pipeline.sentiment,
        emotion=pipeline.emotion,
        risk_score=pipeline.risk_score,
    )
    db.add(msg)

    db.add(EmotionLog(
        user_id=current_user.id,
        sentiment_score=pipeline.sentiment_score,
        emotion=pipeline.emotion,
        emotion_score=pipeline.emotion_score,
        risk_score=pipeline.risk_score,
        source="message",
    ))

    await db.commit()
    await db.refresh(msg)

    # Notify receiver via WebSocket if online
    await manager.send_to_user(body.receiver_id, {
        "type": "new_message",
        "id": msg.id,
        "sender_id": current_user.id,
        "content": body.content,
        "created_at": msg.created_at.isoformat(),
        "sender": {
            "username": current_user.username,
            "avatar_url": current_user.avatar_url,
        },
    })

    return msg


@router.get("/conversations")
async def get_conversations(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get list of conversations with latest message."""
    result = await db.execute(
        select(Message)
        .where(
            or_(
                Message.sender_id == current_user.id,
                Message.receiver_id == current_user.id,
            )
        )
        .order_by(Message.created_at.desc())
    )
    messages = result.scalars().all()

    # Group by conversation partner
    conversations = {}
    for msg in messages:
        partner_id = msg.receiver_id if msg.sender_id == current_user.id else msg.sender_id
        if partner_id not in conversations:
            partner = await db.get(User, partner_id)
            conversations[partner_id] = {
                "user": {
                    "id": partner.id,
                    "username": partner.username,
                    "display_name": partner.display_name,
                    "avatar_url": partner.avatar_url,
                },
                "last_message": {
                    "content": msg.content,
                    "created_at": msg.created_at.isoformat(),
                    "is_mine": msg.sender_id == current_user.id,
                    "sentiment": msg.sentiment,
                },
                "is_online": manager.is_online(partner_id),
                "unread_count": 0,
            }

    return list(conversations.values())


@router.get("/thread/{other_user_id}", response_model=list[MessageOut])
async def get_thread(
    other_user_id: int,
    limit: int = 50,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get message thread between current user and another user."""
    result = await db.execute(
        select(Message)
        .where(
            or_(
                and_(
                    Message.sender_id == current_user.id,
                    Message.receiver_id == other_user_id,
                ),
                and_(
                    Message.sender_id == other_user_id,
                    Message.receiver_id == current_user.id,
                ),
            )
        )
        .order_by(Message.created_at.asc())
        .limit(limit)
    )
    messages = result.scalars().all()

    # Mark as read
    for msg in messages:
        if msg.receiver_id == current_user.id and not msg.is_read:
            msg.is_read = True
    await db.commit()

    return messages


@router.get("/online-status/{user_id}")
async def get_online_status(user_id: int):
    return {"user_id": user_id, "is_online": manager.is_online(user_id)}