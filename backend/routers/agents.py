"""
Agents Router
GET /api/agents/status/{user_id} → latest agent decision
"""

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from models.database import get_db
from models.models import AgentDecision
from schemas.schemas import AgentStatusOut

router = APIRouter()


@router.get("/status/{user_id}", response_model=AgentStatusOut)
async def get_agent_status(user_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(AgentDecision)
        .where(AgentDecision.user_id == user_id)
        .order_by(AgentDecision.timestamp.desc())
        .limit(1)
    )
    row = result.scalar_one_or_none()

    if not row:
        from datetime import datetime
        return AgentStatusOut(
            user_id=user_id,
            risk_level="low",
            decision="monitor",
            intervention="No data yet. Monitoring.",
            rag_suggestion="Take care of yourself. Reach out if you need support.",
            timestamp=datetime.utcnow(),
        )

    return AgentStatusOut(
        user_id=user_id,
        risk_level=row.risk_level,
        decision=row.decision,
        intervention=row.intervention,
        rag_suggestion=row.rag_suggestion,
        timestamp=row.timestamp,
    )


@router.get("/history/{user_id}")
async def get_agent_history(user_id: int, limit: int = 20, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(AgentDecision)
        .where(AgentDecision.user_id == user_id)
        .order_by(AgentDecision.timestamp.desc())
        .limit(limit)
    )
    rows = result.scalars().all()
    return [
        {
            "timestamp": r.timestamp,
            "risk_level": r.risk_level,
            "decision": r.decision,
            "intervention": r.intervention,
        }
        for r in rows
    ]
