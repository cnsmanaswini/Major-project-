import logging

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

# Columns added after initial deploy — create_all() won't alter existing tables.
_POST_MIGRATIONS = [
    ("image_public_id", "VARCHAR(255) DEFAULT ''"),
    ("video_public_id", "VARCHAR(255) DEFAULT ''"),
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


async def create_tables():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        await conn.run_sync(_migrate_posts_table)


async def get_db():
    async with AsyncSessionLocal() as session:
        yield session
