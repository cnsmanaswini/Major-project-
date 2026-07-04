"""
MindGram — Mental Health-Aware Social Media Platform
FastAPI Backend Entry Point
"""
from dotenv import load_dotenv
load_dotenv()

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import logging

from routers import posts, feed, messages, analytics, interactions, agents, users
from routers.auth import router as auth_router
from models.database import create_tables
from ai.pipeline.loader import preload_models
from ai.rag.index import build_rag_index
from config import settings

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("mindgram")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup: initialize DB, preload models, build RAG index."""
    logger.info("🚀 MindGram starting up...")
    await create_tables()
    logger.info("✅ Database tables created")
    try:
        preload_models()
        logger.info("✅ AI models loaded")
    except Exception as e:
        logger.warning(f"⚠️ AI models failed to load: {e}")
    try:
        build_rag_index()
        logger.info("✅ RAG FAISS index built")
    except Exception as e:
        logger.warning(f"⚠️ RAG index failed: {e}")
    yield
    logger.info("🛑 MindGram shutting down")


app = FastAPI(
    title="MindGram API",
    description="Mental Health-Aware Social Media Backend",
    version="2.0.0",
    lifespan=lifespan,
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        settings.FRONTEND_URL,
        "http://localhost:5173",
        "http://localhost:3000",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Routers
app.include_router(auth_router,             prefix="/api/auth",         tags=["Auth"])
app.include_router(users.router,            prefix="/api/users",        tags=["Users"])
app.include_router(posts.router,            prefix="/api/posts",        tags=["Posts"])
app.include_router(feed.router,             prefix="/api/feed",         tags=["Feed"])
app.include_router(messages.router,         prefix="/api/messages",     tags=["Messages"])
app.include_router(analytics.router,        prefix="/api/analytics",    tags=["Analytics"])
app.include_router(interactions.router,     prefix="/api/interactions",  tags=["Interactions"])
app.include_router(agents.router,           prefix="/api/agents",       tags=["Agents"])


@app.get("/")
async def root():
    return {
        "status": "ok",
        "app": settings.APP_NAME,
        "version": "2.0.0",
    }


@app.get("/health")
async def health():
    return {"status": "healthy"}