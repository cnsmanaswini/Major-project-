"""
Analytics Service — aggregates EmotionLog data for the dashboard.
"""

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from collections import Counter
from datetime import datetime, timedelta

from models.models import EmotionLog, AgentDecision
from schemas.schemas import AnalyticsOut, EmotionPoint


async def build_analytics(
    user_id: int,
    db: AsyncSession,
    limit: int = 50,
) -> AnalyticsOut:
    """
    Aggregate emotion logs into dashboard-ready analytics.
    Returns AnalyticsOut with timeline, risk, dominant emotion, avg sentiment.
    """
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
    interventions = [
        l for l in logs
        if l.agent_action and l.agent_action not in ("none", "monitor")
    ]

    return AnalyticsOut(
        user_id=user_id,
        emotion_timeline=timeline,
        current_risk=round(current_risk, 3),
        dominant_emotion=dominant,
        average_sentiment=round(avg_sentiment, 3),
        intervention_count=len(interventions),
    )


async def get_risk_summary(user_id: int, db: AsyncSession) -> dict:
    """Return latest agent decision risk info."""
    result = await db.execute(
        select(AgentDecision)
        .where(AgentDecision.user_id == user_id)
        .order_by(AgentDecision.timestamp.desc())
        .limit(1)
    )
    row = result.scalar_one_or_none()
    if not row:
        return {"user_id": user_id, "risk_level": "low", "risk_score": 0.0, "decision": "monitor"}

    risk_map = {"low": 0.1, "moderate": 0.45, "high": 0.70, "critical": 0.92}
    return {
        "user_id": user_id,
        "risk_level": row.risk_level,
        "risk_score": risk_map.get(row.risk_level, 0.1),
        "decision": row.decision,
        "timestamp": row.timestamp,
    }


async def get_weekly_emotion_counts(user_id: int, db: AsyncSession) -> dict:
    """Count emotion occurrences in the last 7 days — useful for pie charts."""
    cutoff = datetime.utcnow() - timedelta(days=7)
    result = await db.execute(
        select(EmotionLog)
        .where(EmotionLog.user_id == user_id, EmotionLog.timestamp >= cutoff)
    )
    logs = result.scalars().all()
    counts = Counter(log.emotion for log in logs)
    return dict(counts)
