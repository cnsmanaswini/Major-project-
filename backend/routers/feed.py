"""
Feed Router
GET /api/feed/         → personalized feed
GET /api/feed/explore  → discover new content
GET /api/feed/reels    → reels feed
"""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from datetime import datetime, timedelta

from models.database import get_db
from models.models import Post, User, Story
from schemas.schemas import PostOut
from routers.auth import get_current_user, get_optional_user
from services.algorithm import build_feed
from models.models import User as UserModel

router = APIRouter()


@router.get("", response_model=list[PostOut])
async def get_feed(
    limit: int = Query(default=20, le=50),
    offset: int = Query(default=0),
    current_user: UserModel = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Personalized feed using Instagram-like algorithm
    with silent AI mental health layer.
    """
    posts = await build_feed(
        user_id=current_user.id,
        db=db,
        limit=limit,
        offset=offset,
    )
    return posts


@router.get("/explore", response_model=list[PostOut])
async def get_explore(
    limit: int = Query(default=30, le=50),
    current_user: UserModel = Depends(get_optional_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Explore page — discover new content.
    Shows popular posts from all users.
    """
    cutoff = datetime.utcnow() - timedelta(days=14)
    result = await db.execute(
        select(Post)
        .where(Post.created_at >= cutoff)
        .order_by(Post.feed_score.desc(), Post.likes_count.desc())
        .limit(limit)
    )
    posts = result.scalars().all()

    # Load authors
    for p in posts:
        p.author = await db.get(User, p.user_id)

    return posts


@router.get("/reels", response_model=list[PostOut])
async def get_reels(
    limit: int = Query(default=10, le=30),
    current_user: UserModel = Depends(get_optional_user),
    db: AsyncSession = Depends(get_db),
):
    """Reels feed — only video posts."""
    cutoff = datetime.utcnow() - timedelta(days=30)
    result = await db.execute(
        select(Post)
        .where(
            Post.is_reel == True,
            Post.created_at >= cutoff,
        )
        .order_by(Post.feed_score.desc())
        .limit(limit)
    )
    posts = result.scalars().all()
    for p in posts:
        p.author = await db.get(User, p.user_id)
    return posts


@router.get("/stories")
async def get_stories(
    current_user: UserModel = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Get stories from followed users.
    Stories expire after 24 hours.
    """
    from models.models import Follow
    # Get following ids
    result = await db.execute(
        select(Follow.following_id)
        .where(Follow.follower_id == current_user.id)
    )
    following_ids = [r[0] for r in result.fetchall()]
    following_ids.append(current_user.id)  # include own stories

    # Get active stories
    cutoff = datetime.utcnow() - timedelta(hours=24)
    stories_result = await db.execute(
        select(Story)
        .where(
            Story.user_id.in_(following_ids),
            Story.created_at >= cutoff,
        )
        .order_by(Story.created_at.desc())
    )
    stories = stories_result.scalars().all()

    # Group by user
    stories_by_user = {}
    for story in stories:
        uid = story.user_id
        if uid not in stories_by_user:
            user = await db.get(User, uid)
            stories_by_user[uid] = {
                "user": {
                    "id": user.id,
                    "username": user.username,
                    "display_name": user.display_name,
                    "avatar_url": user.avatar_url,
                },
                "stories": [],
            }
        stories_by_user[uid]["stories"].append({
            "id": story.id,
            "image_url": story.image_url,
            "video_url": story.video_url,
            "text": story.text,
            "created_at": story.created_at,
        })

    return list(stories_by_user.values())