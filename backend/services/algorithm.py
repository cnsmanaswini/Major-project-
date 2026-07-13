"""
MindGram Feed Algorithm
Instagram-inspired ranking + Silent AI mental health layer

Ranking factors:
1. Interest Score    → based on what you engage with
2. Relationship Score → how often you interact with someone
3. Recency           → newer posts ranked higher
4. Engagement        → likes + comments + shares
5. Silent AI Layer   → suppress negative content for at-risk users
                     → promote positive content gently
"""

import math
from datetime import datetime, timedelta
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from collections import defaultdict

from models.models import (
    Post, User, Like, Comment, Follow,
    AgentDecision, EmotionLog, UserInterest
)


# ── Constants ─────────────────────────────────────────────────

RECENCY_HALF_LIFE_HOURS = 48.0
RISK_SUPPRESSION_THRESHOLD = 0.60

async def attach_like_status(posts, user_id: int, db: AsyncSession):
    """Mutates posts in-place, setting `is_liked` based on whether
    `user_id` has a Like row for each post. One query for the whole batch."""
    if not posts:
        return posts
    post_ids = [p.id for p in posts]
    result = await db.execute(
        select(Like.post_id).where(
            Like.post_id.in_(post_ids),
            Like.user_id == user_id,
        )
    )
    liked_ids = {row[0] for row in result.all()}
    for p in posts:
        p.is_liked = p.id in liked_ids
    return posts
    
WEIGHTS = {
    "interest":     0.30,
    "relationship": 0.25,
    "recency":      0.20,
    "engagement":   0.15,
    "ai_quality":   0.10,
}


# ── Individual Scoring Functions ──────────────────────────────

def recency_score(created_at: datetime) -> float:
    """Exponential decay — newer posts score higher."""
    age_hours = (datetime.utcnow() - created_at).total_seconds() / 3600.0
    return round(math.exp(-age_hours / RECENCY_HALF_LIFE_HOURS), 4)


def engagement_score(post: Post) -> float:
    """Normalized engagement score."""
    score = (
        post.likes_count * 1.0 +
        post.comments_count * 2.0 +
        post.shares_count * 3.0 +
        post.views_count * 0.1
    )
    return min(1.0, score / 200.0)


def interest_score(post: Post, user_interests: dict) -> float:
    """
    How likely is this user to be interested in this post?
    Based on what emotions/content they've engaged with before.
    """
    if not user_interests:
        return 0.5  # neutral for new users

    emotion = post.emotion or "neutral"
    return user_interests.get(emotion, 0.3)


def relationship_score(post: Post, interaction_counts: dict) -> float:
    """
    How close is this user to the post author?
    Based on number of past interactions.
    """
    count = interaction_counts.get(post.user_id, 0)
    return min(1.0, count / 20.0)


def silent_ai_adjustment(
    post: Post,
    user_risk: float,
) -> float:
    """
    Silent mental health adjustment.
    For at-risk users:
      - Suppress high-risk negative content
      - Boost positive content
    User never sees this happening.
    """
    adjustment = 0.0

    if user_risk >= RISK_SUPPRESSION_THRESHOLD:
        # Suppress negative/risky content
        if post.risk_score > 0.5:
            penalty = (post.risk_score - 0.5) * user_risk * 0.5
            adjustment -= penalty

        # Boost positive content
        if post.sentiment == "positive" and post.risk_score < 0.2:
            boost = (1.0 - user_risk) * 0.2
            adjustment += boost

    return adjustment


# ── Main Ranking Function ─────────────────────────────────────

def compute_rank(
    post: Post,
    user_risk: float,
    user_interests: dict,
    interaction_counts: dict,
) -> float:
    """
    Compute final rank score for a post.
    Combines all signals with weights.
    """
    scores = {
        "interest":     interest_score(post, user_interests),
        "relationship": relationship_score(post, interaction_counts),
        "recency":      recency_score(post.created_at),
        "engagement":   engagement_score(post),
        "ai_quality":   post.feed_score,
    }

    # Weighted sum
    rank = sum(scores[k] * WEIGHTS[k] for k in scores)

    # Apply silent AI adjustment
    rank += silent_ai_adjustment(post, user_risk)

    return round(max(0.0, min(1.0, rank)), 4)


# ── Wellness Content Injection ────────────────────────────────

def should_inject_wellness(user_risk: float, position: int) -> bool:
    """
    Decide if we should inject a wellness post at this feed position.
    Only for at-risk users, naturally placed at position 5 or 10.
    """
    if user_risk < RISK_SUPPRESSION_THRESHOLD:
        return False
    return position in (5, 10)


# ── Feed Builder ──────────────────────────────────────────────

async def build_feed(
    user_id: int,
    db: AsyncSession,
    limit: int = 20,
    offset: int = 0,
) -> list[Post]:
    """
    Build the personalized feed for a user.

    Steps:
    1. Get user's risk level (silent)
    2. Get user's interests from engagement history
    3. Get user's relationship scores
    4. Fetch candidate posts (from followed users + explore)
    5. Rank all posts
    6. Return top N
    """

    # 1 — Get user risk level
    agent_result = await db.execute(
        select(AgentDecision)
        .where(AgentDecision.user_id == user_id)
        .order_by(AgentDecision.timestamp.desc())
        .limit(1)
    )
    agent_row = agent_result.scalar_one_or_none()
    risk_map = {"low": 0.1, "moderate": 0.45, "high": 0.70, "critical": 0.92}
    user_risk = risk_map.get(agent_row.risk_level, 0.1) if agent_row else 0.1

    # 2 — Get user interests
    interest_result = await db.execute(
        select(UserInterest).where(UserInterest.user_id == user_id)
    )
    interests = interest_result.scalars().all()
    user_interests = {i.emotion: i.score for i in interests}

    # 3 — Get interaction counts (who user interacts with most)
    following_result = await db.execute(
        select(Follow.following_id)
        .where(Follow.follower_id == user_id)
    )
    following_ids = [r[0] for r in following_result.fetchall()]

    # Count likes on their posts as relationship signal
    interaction_counts = defaultdict(int)
    if following_ids:
        like_result = await db.execute(
            select(Post.user_id, func.count(Like.id))
            .join(Like, Like.post_id == Post.id)
            .where(Like.user_id == user_id)
            .group_by(Post.user_id)
        )
        for author_id, count in like_result.fetchall():
            interaction_counts[author_id] = count

    # 4 — Fetch candidate posts
    cutoff = datetime.utcnow() - timedelta(days=7)

    # Posts from followed users
    if following_ids:
        followed_result = await db.execute(
            select(Post)
            .where(
                Post.user_id.in_(following_ids),
                Post.created_at >= cutoff,
            )
            .order_by(Post.created_at.desc())
            .limit(100)
        )
        followed_posts = followed_result.scalars().all()
    else:
        followed_posts = []

    # Explore posts (from non-followed users)
    explore_result = await db.execute(
        select(Post)
        .where(
            Post.user_id != user_id,
            Post.created_at >= cutoff,
        )
        .order_by(Post.feed_score.desc())
        .limit(50)
    )
    explore_posts = explore_result.scalars().all()

    # Combine and deduplicate
    seen_ids = set()
    all_posts = []
    for p in followed_posts + explore_posts:
        if p.id not in seen_ids:
            seen_ids.add(p.id)
            all_posts.append(p)

    # Load authors
    author_cache = {}
    for p in all_posts:
        if p.user_id not in author_cache:
            author_cache[p.user_id] = await db.get(User, p.user_id)
        p.author = author_cache[p.user_id]

    # 5 — Rank posts
    all_posts.sort(
        key=lambda p: compute_rank(p, user_risk, user_interests, interaction_counts),
        reverse=True,
    )

    # 6 — Return paginated results
    return all_posts[offset:offset + limit]


async def update_user_interests(
    user_id: int,
    emotion: str,
    db: AsyncSession,
    weight: float = 0.1,
):
    """
    Update user interest scores when they engage with content.
    Called when user likes or comments on a post.
    """
    result = await db.execute(
        select(UserInterest).where(
            UserInterest.user_id == user_id,
            UserInterest.emotion == emotion,
        )
    )
    interest = result.scalar_one_or_none()

    if interest:
        # Exponential moving average
        interest.score = min(1.0, interest.score * 0.9 + weight)
        interest.updated_at = datetime.utcnow()
    else:
        db.add(UserInterest(
            user_id=user_id,
            emotion=emotion,
            score=weight,
        ))

    await db.commit()