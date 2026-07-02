"""
Analytics Router
GET /api/analytics/{user_id}         → full emotional analytics
GET /api/analytics/{user_id}/summary → lightweight summary
GET /api/risk/{user_id}              → current risk score
GET /api/suggestions/{user_id}       → RAG suggestions
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from collections import Counter
from datetime import datetime

from models.database import get_db
from models.models import EmotionLog, AgentDecision
from schemas.schemas import AnalyticsOut, EmotionPoint, AgentStatusOut
from ai.rag.index import retrieve_top_k

router = APIRouter()


@router.get("/{user_id}", response_model=AnalyticsOut)
async def get_analytics(user_id: int, limit: int = 50, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(EmotionLog)
        .where(EmotionLog.user_id == user_id)
        .order_by(EmotionLog.timestamp.asc())
        .limit(limit)
    )
    logs = result.scalars().all()

    if not logs:
        return AnalyticsOut(
            user_id=user_id,
            emotion_timeline=[],
            current_risk=0.0,
            dominant_emotion="neutral",
            average_sentiment=0.0,
            intervention_count=0,
        )

    timeline = [
        EmotionPoint(
            timestamp=log.timestamp,
            sentiment_score=log.sentiment_score,
            emotion=log.emotion,
            risk_score=log.risk_score,
            agent_action=log.agent_action or "none",
        )
        for log in logs
    ]

    emotions = [log.emotion for log in logs]
    dominant = Counter(emotions).most_common(1)[0][0]
    avg_sentiment = sum(log.sentiment_score for log in logs) / len(logs)
    current_risk = logs[-1].risk_score

    interventions = [l for l in logs if l.agent_action and l.agent_action != "none" and l.agent_action != "monitor"]

    return AnalyticsOut(
        user_id=user_id,
        emotion_timeline=timeline,
        current_risk=round(current_risk, 3),
        dominant_emotion=dominant,
        average_sentiment=round(avg_sentiment, 3),
        intervention_count=len(interventions),
    )


@router.get("/{user_id}/risk")
async def get_risk(user_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(AgentDecision)
        .where(AgentDecision.user_id == user_id)
        .order_by(AgentDecision.timestamp.desc())
        .limit(1)
    )
    row = result.scalar_one_or_none()
    if not row:
        return {"user_id": user_id, "risk_level": "low", "risk_score": 0.0}
    return {
        "user_id": user_id,
        "risk_level": row.risk_level,
        "decision": row.decision,
        "timestamp": row.timestamp,
    }


@router.get("/{user_id}/suggestions")
async def get_suggestions(user_id: int, db: AsyncSession = Depends(get_db)):
    """Retrieve top-3 RAG suggestions based on user's recent emotional state."""
    result = await db.execute(
        select(EmotionLog)
        .where(EmotionLog.user_id == user_id)
        .order_by(EmotionLog.timestamp.desc())
        .limit(5)
    )
    logs = result.scalars().all()

    if not logs:
        context = "general wellness self-care"
    else:
        recent_emotions = " ".join([log.emotion for log in logs])
        avg_sent = sum(log.sentiment_score for log in logs) / len(logs)
        polarity = "negative" if avg_sent < -0.1 else "positive"
        context = f"{polarity} feeling {recent_emotions}"

    suggestions = retrieve_top_k(context, top_k=3)
    return {"user_id": user_id, "context": context, "suggestions": suggestions}
