"""
Feed Service — adaptive re-ranking engine.
Separated from the router so it can be tested and reused independently.
"""

import math
from datetime import datetime, timedelta
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from models.models import Post, User, AgentDecision

RECENCY_HALF_LIFE_HOURS = 24.0
RISK_SUPPRESSION_THRESHOLD = 0.60

RISK_LEVEL_MAP = {
    "low": 0.10,
    "moderate": 0.45,
    "high": 0.70,
    "critical": 0.92,
}


def recency_score(created_at: datetime) -> float:
    """
    Exponential decay over time.
    A post created now scores ~1.0; one created 24h ago scores ~0.37.
    """
    age_hours = (datetime.utcnow() - created_at).total_seconds() / 3600.0
    return round(math.exp(-age_hours / RECENCY_HALF_LIFE_HOURS), 4)


def compute_adaptive_rank(post: Post, user_risk: float) -> float:
    """
    Composite adaptive rank ∈ [0, 1].

    Weights:
      - feed_score (AI positivity + baseline engagement): 45%
      - recency:                                          30%
      - engagement (likes + 2×comments / 50):            25%

    Penalty:
      - If user_risk ≥ threshold AND post.risk_score > 0.5:
        apply a suppression penalty proportional to both.
    """
    base       = post.feed_score
    recency    = recency_score(post.created_at)
    engagement = min(1.0, (post.likes_count + post.comments_count * 2) / 50.0)

    score = base * 0.45 + recency * 0.30 + engagement * 0.25

    if user_risk >= RISK_SUPPRESSION_THRESHOLD and post.risk_score > 0.5:
        penalty = (post.risk_score - 0.5) * user_risk * 0.4
        score -= penalty

    return round(max(0.0, min(1.0, score)), 4)


async def get_adaptive_feed(
    user_id: int,
    db: AsyncSession,
    limit: int = 20,
    pool_days: int = 7,
) -> list[Post]:
    """
    Fetch a pool of recent posts and re-rank them adaptively based on:
      - The requesting user's current mental health risk level
      - Each post's AI-generated feed score, recency, and engagement

    Returns up to `limit` posts, highest-ranked first.
    """
    # Determine user's current risk level from latest agent decision
    agent_result = await db.execute(
        select(AgentDecision)
        .where(AgentDecision.user_id == user_id)
        .order_by(AgentDecision.timestamp.desc())
        .limit(1)
    )
    agent_row = agent_result.scalar_one_or_none()
    user_risk = RISK_LEVEL_MAP.get(agent_row.risk_level, 0.0) if agent_row else 0.0

    # Fetch candidate pool
    cutoff = datetime.utcnow() - timedelta(days=pool_days)
    result = await db.execute(
        select(Post)
        .where(Post.created_at >= cutoff)
        .order_by(Post.created_at.desc())
        .limit(200)
    )
    posts = result.scalars().all()

    # Cache author lookups
    author_cache: dict[int, User] = {}
    for p in posts:
        if p.user_id not in author_cache:
            author_cache[p.user_id] = await db.get(User, p.user_id)
        p.author = author_cache[p.user_id]

    # Rank and slice
    posts.sort(key=lambda p: compute_adaptive_rank(p, user_risk), reverse=True)
    return posts[:limit]
