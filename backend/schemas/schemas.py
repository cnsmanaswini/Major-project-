"""
Pydantic schemas for MindGram API
"""

from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime


# ── User ────────────────────────────────────────────────────

class UserCreate(BaseModel):
    username: str
    display_name: str
    avatar_url: Optional[str] = ""
    bio: Optional[str] = ""


class UserOut(BaseModel):
    id: int
    username: str
    display_name: str
    avatar_url: str
    bio: str
    created_at: datetime

    class Config:
        from_attributes = True


# ── Post ────────────────────────────────────────────────────

class PostCreate(BaseModel):
    user_id: int
    content: str
    image_url: Optional[str] = ""
    video_url: Optional[str] = ""
    location: Optional[str] = ""
    is_reel: bool = False


class PostOut(BaseModel):
    id: int
    user_id: int
    content: str
    image_url: str
    video_url: str
    is_reel: bool
    location: str
    created_at: datetime
    sentiment: str
    sentiment_score: float
    emotion: str
    emotion_score: float
    sarcasm: bool
    sarcasm_score: float
    risk_score: float
    feed_score: float
    likes_count: int
    comments_count: int
    is_liked: bool = False          # ← ADD THIS LINE
    author: Optional[UserOut] = None

    class Config:
        from_attributes = True


# ── Comment ─────────────────────────────────────────────────

class CommentCreate(BaseModel):
    post_id: int
    user_id: int
    content: str


class CommentOut(BaseModel):
    id: int
    post_id: int
    user_id: int
    content: str
    created_at: datetime
    sentiment: str
    user: Optional[UserOut] = None

    class Config:
        from_attributes = True


# ── Message ─────────────────────────────────────────────────

class MessageCreate(BaseModel):
    sender_id: int
    receiver_id: int
    content: str


class MessageOut(BaseModel):
    id: int
    sender_id: int
    receiver_id: int
    content: str
    created_at: datetime
    sentiment: str
    emotion: str
    risk_score: float

    class Config:
        from_attributes = True


# ── Interaction ─────────────────────────────────────────────

class InteractionCreate(BaseModel):
    user_id: int
    post_id: int
    action: str  # like | unlike | comment | share


# ── Analytics ───────────────────────────────────────────────

class EmotionPoint(BaseModel):
    timestamp: datetime
    sentiment_score: float
    emotion: str
    risk_score: float
    agent_action: str


class AnalyticsOut(BaseModel):
    user_id: int
    emotion_timeline: List[EmotionPoint]
    current_risk: float
    dominant_emotion: str
    average_sentiment: float
    intervention_count: int


# ── Agents ──────────────────────────────────────────────────

class AgentStatusOut(BaseModel):
    user_id: int
    risk_level: str
    decision: str
    intervention: str
    rag_suggestion: str
    timestamp: datetime

    class Config:
        from_attributes = True


# ── AI Pipeline Internal ─────────────────────────────────────

class PipelineResult(BaseModel):
    sentiment: str
    sentiment_score: float
    emotion: str
    emotion_score: float
    sarcasm: bool
    sarcasm_score: float
    risk_score: float
    feed_score: float