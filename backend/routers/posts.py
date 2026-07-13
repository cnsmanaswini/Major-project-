"""
Posts Router
POST /api/posts          → create post with image/video upload
GET  /api/posts/{id}     → get single post
DELETE /api/posts/{id}   → delete post
POST /api/posts/{id}/like → like/unlike post
"""

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import Optional
from datetime import datetime

from models.database import get_db
from models.models import (
    Post, User, EmotionLog, AgentDecision,
    Like, Notification
)
from schemas.schemas import PostOut, UserOut
from routers.auth import get_current_user, get_optional_user
from services.algorithm import attach_like_status, update_user_interests
from ai.pipeline.analyzer import analyze_text
from ai.agents.orchestrator import run_agents, EmotionSnapshot
from services.cloudinary_service import upload_image, upload_video, delete_asset

router = APIRouter()


async def get_user_risk_history(user_id: int, db: AsyncSession) -> list[float]:
    result = await db.execute(
        select(EmotionLog.risk_score)
        .where(EmotionLog.user_id == user_id)
        .order_by(EmotionLog.timestamp.desc())
        .limit(20)
    )
    rows = result.scalars().all()
    return list(reversed(rows))


async def get_emotion_history(user_id: int, db: AsyncSession) -> list[EmotionSnapshot]:
    result = await db.execute(
        select(EmotionLog)
        .where(EmotionLog.user_id == user_id)
        .order_by(EmotionLog.timestamp.desc())
        .limit(20)
    )
    logs = result.scalars().all()
    return [
        EmotionSnapshot(
            sentiment_score=log.sentiment_score,
            emotion=log.emotion,
            emotion_score=log.emotion_score,
            risk_score=log.risk_score,
            source=log.source,
        )
        for log in reversed(logs)
    ]


@router.post("", response_model=PostOut, status_code=201)
async def create_post(
    content: str = Form(default=""),
    location: str = Form(default=""),
    is_reel: bool = Form(default=False),
    image: Optional[UploadFile] = File(default=None),
    video: Optional[UploadFile] = File(default=None),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if not content and not image and not video:
        raise HTTPException(
            status_code=400,
            detail="Post must have content, image or video"
        )

    image_url = ""
    video_url = ""
    image_public_id = ""
    video_public_id = ""

    # Upload media to Cloudinary
    if image and image.filename:
        result = await upload_image(image, folder="mindgram/posts")
        image_url = result["url"]
        image_public_id = result["public_id"]

    if video and video.filename:
        result = await upload_video(video, folder="mindgram/reels")
        video_url = result["url"]
        video_public_id = result["public_id"]
        is_reel = True

    # Run AI pipeline on caption (or a neutral default for image-only posts)
    text_to_analyze = content.strip() or ("shared a photo" if image_url else "shared a video" if video_url else "photo post")
    risk_history = await get_user_risk_history(current_user.id, db)
    pipeline = analyze_text(text_to_analyze, risk_history)

    # Create post
    post = Post(
        user_id=current_user.id,
        content=content,
        image_url=image_url,
        video_url=video_url,
        image_public_id=image_public_id,
        video_public_id=video_public_id,
        is_reel=is_reel,
        location=location,
        sentiment=pipeline.sentiment,
        sentiment_score=pipeline.sentiment_score,
        emotion=pipeline.emotion,
        emotion_score=pipeline.emotion_score,
        sarcasm=pipeline.sarcasm,
        sarcasm_score=pipeline.sarcasm_score,
        risk_score=pipeline.risk_score,
        feed_score=pipeline.feed_score,
    )
    db.add(post)

    # Log emotion
    log = EmotionLog(
        user_id=current_user.id,
        sentiment_score=pipeline.sentiment_score,
        emotion=pipeline.emotion,
        emotion_score=pipeline.emotion_score,
        risk_score=pipeline.risk_score,
        source="post",
    )
    db.add(log)

    # Update post count
    current_user.posts_count = (current_user.posts_count or 0) + 1

    await db.flush()

    # Run agentic pipeline
    history = await get_emotion_history(current_user.id, db)
    current_snap = EmotionSnapshot(
        sentiment_score=pipeline.sentiment_score,
        emotion=pipeline.emotion,
        emotion_score=pipeline.emotion_score,
        risk_score=pipeline.risk_score,
        source="post",
    )
    agent_report = run_agents(current_snap, history)

    # Save agent decision
    db.add(AgentDecision(
        user_id=current_user.id,
        risk_level=agent_report.risk_level,
        decision=agent_report.decision,
        intervention=agent_report.intervention,
        rag_suggestion=agent_report.rag_suggestion,
        metadata_json=agent_report.metadata,
    ))
    log.agent_action = agent_report.decision

    await db.commit()
    await db.refresh(post)
    post.author = current_user
    return post


@router.get("/{post_id}", response_model=PostOut)
async def get_post(
    post_id: int,
    current_user: Optional[User] = Depends(get_optional_user),
    db: AsyncSession = Depends(get_db),
):
    post = await db.get(Post, post_id)
    if not post:
        raise HTTPException(status_code=404, detail="Post not found")
    post.author = await db.get(User, post.user_id)
    if current_user:
        await attach_like_status([post], current_user.id, db)
    return post
    


@router.delete("/{post_id}")
async def delete_post(
    post_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    post = await db.get(Post, post_id)
    if not post:
        raise HTTPException(status_code=404, detail="Post not found")
    if post.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not your post")

    # Clean up Cloudinary storage before deleting the DB row.
    # Best-effort: delete_asset() already swallows its own errors,
    # so a Cloudinary hiccup never blocks the actual post deletion.
    if post.image_public_id:
        delete_asset(post.image_public_id, resource_type="image")
    if post.video_public_id:
        delete_asset(post.video_public_id, resource_type="video")

    await db.delete(post)
    current_user.posts_count = max(0, (current_user.posts_count or 1) - 1)
    await db.commit()
    return {"status": "deleted"}


@router.post("/{post_id}/like")
async def toggle_like(
    post_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    post = await db.get(Post, post_id)
    if not post:
        raise HTTPException(status_code=404, detail="Post not found")

    # Check if already liked
    result = await db.execute(
        select(Like).where(
            Like.post_id == post_id,
            Like.user_id == current_user.id,
        )
    )
    existing = result.scalar_one_or_none()

    if existing:
        # Unlike
        await db.delete(existing)
        post.likes_count = max(0, post.likes_count - 1)
        action = "unliked"
    else:
        # Like
        db.add(Like(post_id=post_id, user_id=current_user.id))
        post.likes_count += 1
        action = "liked"

        # Update user interests based on post emotion
        await update_user_interests(current_user.id, post.emotion, db)

        # Notify post author
        if post.user_id != current_user.id:
            db.add(Notification(
                user_id=post.user_id,
                from_user_id=current_user.id,
                type="like",
                message=f"{current_user.username} liked your post",
                post_id=post_id,
            ))

    await db.commit()
    return {
        "status": action,
        "is_liked": action == "liked",
        "likes_count": post.likes_count,
    }
    

@router.get("/{post_id}/likes", response_model=list[UserOut])
async def get_post_likers(
    post_id: int,
    limit: int = 50,
    offset: int = 0,
    db: AsyncSession = Depends(get_db),
):
    """List of users who liked this post, most recent first."""
    post = await db.get(Post, post_id)
    if not post:
        raise HTTPException(status_code=404, detail="Post not found")

    result = await db.execute(
        select(User)
        .join(Like, Like.user_id == User.id)
        .where(Like.post_id == post_id)
        .order_by(Like.created_at.desc())
        .limit(limit)
        .offset(offset)
    )
    return result.scalars().all()

@router.get("/user/{user_id}", response_model=list[PostOut])
async def get_user_posts(
    user_id: int,
    limit: int = 20,
    offset: int = 0,
    current_user: Optional[User] = Depends(get_optional_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Post)
        .where(Post.user_id == user_id)
        .order_by(Post.created_at.desc())
        .limit(limit)
        .offset(offset)
    )
    posts = result.scalars().all()
    user = await db.get(User, user_id)
    for p in posts:
        p.author = user
    if current_user:
        await attach_like_status(posts, current_user.id, db)
    return posts