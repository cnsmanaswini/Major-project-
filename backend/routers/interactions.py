"""
Interactions Router — likes, comments, shares
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from models.database import get_db
from models.models import Post, Like, Comment, User
from schemas.schemas import InteractionCreate, CommentCreate, CommentOut
from ai.pipeline.analyzer import analyze_text

router = APIRouter()


@router.post("")
async def record_interaction(body: InteractionCreate, db: AsyncSession = Depends(get_db)):
    post = await db.get(Post, body.post_id)
    if not post:
        raise HTTPException(status_code=404, detail="Post not found")

    if body.action == "like":
        like = Like(post_id=body.post_id, user_id=body.user_id)
        db.add(like)
        post.likes_count += 1

    elif body.action == "unlike":
        result = await db.execute(
            select(Like).where(Like.post_id == body.post_id, Like.user_id == body.user_id)
        )
        like = result.scalar_one_or_none()
        if like:
            await db.delete(like)
            post.likes_count = max(0, post.likes_count - 1)

    await db.commit()
    return {"status": "ok", "action": body.action, "post_id": body.post_id}


@router.post("/comment", response_model=CommentOut, status_code=201)
async def add_comment(body: CommentCreate, db: AsyncSession = Depends(get_db)):
    post = await db.get(Post, body.post_id)
    if not post:
        raise HTTPException(status_code=404, detail="Post not found")

    pipeline = analyze_text(body.content)
    comment = Comment(
        post_id=body.post_id,
        user_id=body.user_id,
        content=body.content,
        sentiment=pipeline.sentiment,
    )
    db.add(comment)
    post.comments_count += 1
    await db.commit()
    await db.refresh(comment)
    comment.user = await db.get(User, body.user_id)
    return comment


@router.get("/comments/{post_id}", response_model=list[CommentOut])
async def get_comments(post_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(Comment).where(Comment.post_id == post_id).order_by(Comment.created_at.asc())
    )
    comments = result.scalars().all()
    for c in comments:
        c.user = await db.get(User, c.user_id)
    return comments
