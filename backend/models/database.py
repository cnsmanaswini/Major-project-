import logging
import json

from sqlalchemy import inspect, text
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from models.models import Base

logger = logging.getLogger("mindgram.db")

DATABASE_URL = "sqlite+aiosqlite:///./mindgram.db"

engine = create_async_engine(DATABASE_URL, echo=False)

AsyncSessionLocal = sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
)

_POST_MIGRATIONS = [
    ("image_public_id", "VARCHAR(255) DEFAULT ''"),
    ("video_public_id", "VARCHAR(255) DEFAULT ''"),
    ("topics", "JSON"),
]


def _migrate_posts_table(connection) -> None:
    inspector = inspect(connection)
    if "posts" not in inspector.get_table_names():
        return

    existing = {col["name"] for col in inspector.get_columns("posts")}
    for column_name, column_def in _POST_MIGRATIONS:
        if column_name not in existing:
            connection.execute(
                text(f"ALTER TABLE posts ADD COLUMN {column_name} {column_def}")
            )
            logger.info("Added posts.%s", column_name)


def _backfill_post_media(connection) -> None:
    inspector = inspect(connection)
    tables = set(inspector.get_table_names())
    if "posts" not in tables or "post_media" not in tables:
        return

    existing = connection.execute(text("SELECT COUNT(*) FROM post_media")).scalar() or 0
    if existing:
        return

    posts = connection.execute(text(
        """
        SELECT id, image_url, video_url, image_public_id, video_public_id
        FROM posts
        WHERE COALESCE(image_url, '') != '' OR COALESCE(video_url, '') != ''
        """
    )).mappings()
    for post in posts:
        position = 0
        if post["image_url"]:
            connection.execute(text(
                """
                INSERT INTO post_media (post_id, media_type, url, public_id, position, created_at)
                VALUES (:post_id, 'image', :url, :public_id, :position, CURRENT_TIMESTAMP)
                """
            ), {
                "post_id": post["id"],
                "url": post["image_url"],
                "public_id": post["image_public_id"] or "",
                "position": position,
            })
            position += 1
        if post["video_url"]:
            connection.execute(text(
                """
                INSERT INTO post_media (post_id, media_type, url, public_id, position, created_at)
                VALUES (:post_id, 'video', :url, :public_id, :position, CURRENT_TIMESTAMP)
                """
            ), {
                "post_id": post["id"],
                "url": post["video_url"],
                "public_id": post["video_public_id"] or "",
                "position": position,
            })
    logger.info("Backfilled post_media from legacy post columns")


def _backfill_post_topics(connection) -> None:
    """Populate topics from existing captions for posts created before the column existed."""
    inspector = inspect(connection)
    if "posts" not in inspector.get_table_names():
        return

    columns = {col["name"] for col in inspector.get_columns("posts")}
    if "topics" not in columns:
        return

    from services.topic_utils import extract_topics

    rows = connection.execute(text(
        "SELECT id, content, emotion, location, topics FROM posts"
    )).mappings()

    for row in rows:
        existing = row["topics"]
        if existing and existing != "[]" and existing != []:
            continue
        topics = extract_topics(row["content"] or "", row["emotion"] or "", row["location"] or "")
        connection.execute(
            text("UPDATE posts SET topics = :topics WHERE id = :id"),
            {"topics": json.dumps(topics), "id": row["id"]},
        )

    logger.info("Backfilled post topics from captions")


async def create_tables():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        await conn.run_sync(_migrate_posts_table)
        await conn.run_sync(_backfill_post_media)
        await conn.run_sync(_backfill_post_topics)


async def get_db():
    async with AsyncSessionLocal() as session:
        yield session
