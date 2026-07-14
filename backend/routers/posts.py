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
from sqlalchemy.orm import selectinload
from typing import Optional
from datetime import datetime

from models.database import get_db
from models.models import (
    Post, User, EmotionLog, AgentDecision,
    Like, Notification, PostMedia
)
from schemas.schemas import PostOut
from routers.auth import get_current_user
from services.topic_utils import extract_topics
from ai.pipeline.analyzer import analyze_text
from ai.agents.orchestrator import run_agents, EmotionSnapshot
from services.cloudinary_service import upload_image, upload_video, delete_asset
from services.algorithm import update_user_interests

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
    images: Optional[list[UploadFile]] = File(default=None),
    image: Optional[UploadFile] = File(default=None),
    video: Optional[UploadFile] = File(default=None),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    image_files = [file for file in (images or []) if file and file.filename]
    if image and image.filename:
        image_files.append(image)

    if len(image_files) > 10:
        raise HTTPException(status_code=400, detail="You can add up to 10 photos per post")

    if image_files and video and video.filename:
        raise HTTPException(status_code=400, detail="Use either a photo carousel or one video, not both")

    if not content and not image_files and not (video and video.filename):
        raise HTTPException(
            status_code=400,
            detail="Post must have content, image or video"
        )

    uploaded_media = []

    # Upload media to Cloudinary
    for position, image_file in enumerate(image_files):
        result = await upload_image(image_file, folder="mindgram/posts")
        uploaded_media.append({
            "media_type": "image",
            "url": result["url"],
            "public_id": result["public_id"],
            "position": position,
        })

    if video and video.filename:
        result = await upload_video(video, folder="mindgram/reels")
        uploaded_media.append({
            "media_type": "video",
            "url": result["url"],
            "public_id": result["public_id"],
            "position": 0,
        })
        is_reel = True

    first_image = next((m for m in uploaded_media if m["media_type"] == "image"), None)
    first_video = next((m for m in uploaded_media if m["media_type"] == "video"), None)

    # Run AI pipeline on caption (or a neutral default for image-only posts)
    text_to_analyze = content.strip() or (
        "shared a photo carousel"
        if len(image_files) > 1
        else "shared a photo"
        if first_image
        else "shared a video"
        if first_video
        else "photo post"
    )
    risk_history = await get_user_risk_history(current_user.id, db)
    pipeline = analyze_text(text_to_analyze, risk_history)

    # Create post
    post = Post(
        user_id=current_user.id,
        content=content,
        image_url=first_image["url"] if first_image else "",
        video_url=first_video["url"] if first_video else "",
        image_public_id=first_image["public_id"] if first_image else "",
        video_public_id=first_video["public_id"] if first_video else "",
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
        topics=extract_topics(content, pipeline.emotion, location),
    )
    db.add(post)
    await db.flush()  # assigns post.id, needed before creating PostMedia rows below

    # IMPORTANT: don't do `post.media = [...]` here.
    # Assigning a list to an async relationship forces SQLAlchemy to lazy-load
    # the existing collection first to diff against it, which fires a sync-style
    # query the async session can't service inline -> MissingGreenlet.
    # Setting post_id explicitly and adding each row individually sidesteps
    # the relationship's collection-loading logic entirely.
    for item in uploaded_media:
        db.add(PostMedia(
            post_id=post.id,
            media_type=item["media_type"],
            url=item["url"],
            public_id=item["public_id"],
            position=item["position"],
        ))

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

    # Explicitly (re)load the media relationship via an awaited query instead
    # of a plain db.refresh(post), which would NOT reload `media` and could
    # trigger the same MissingGreenlet error later when PostOut serializes
    # post.media (an implicit lazy-load on the way out).
    await db.refresh(post, attribute_names=["media"])
    post.author = current_user
    return post


@router.get("/{post_id}", response_model=PostOut)
async def get_post(
    post_id: int,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Post)
        .options(selectinload(Post.media))
        .where(Post.id == post_id)
    )
    post = result.scalar_one_or_none()
    if not post:
        raise HTTPException(status_code=404, detail="Post not found")
    post.author = await db.get(User, post.user_id)
    return post


@router.delete("/{post_id}")
async def delete_post(
    post_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Post)
        .options(selectinload(Post.media))
        .where(Post.id == post_id)
    )
    post = result.scalar_one_or_none()
    if not post:
        raise HTTPException(status_code=404, detail="Post not found")
    if post.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not your post")

    # Clean up Cloudinary storage before deleting the DB row.
    # Best-effort: delete_asset() already swallows its own errors,
    # so a Cloudinary hiccup never blocks the actual post deletion.
    for media in post.media:
        delete_asset(media.public_id, resource_type=media.media_type)

    if not post.media and post.image_public_id:
        delete_asset(post.image_public_id, resource_type="image")
    if not post.media and post.video_public_id:
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
        "likes_count": post.likes_count,
    }


@router.get("/user/{user_id}", response_model=list[PostOut])
async def get_user_posts(
    user_id: int,
    limit: int = 20,
    offset: int = 0,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Post)
        .options(selectinload(Post.media))
        .where(Post.user_id == user_id)
        .order_by(Post.created_at.desc())
        .limit(limit)
        .offset(offset)
    )
    posts = result.scalars().all()
    user = await db.get(User, user_id)
    for p in posts:
        p.author = user
    return posts