from collections.abc import AsyncGenerator

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from app.config import settings

engine = create_async_engine(settings.database_url, echo=False)
async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with async_session() as session:
        yield session


async def _migrate(conn) -> None:
    migrations = [
        "ALTER TABLE documents ADD COLUMN source_type VARCHAR(16) DEFAULT 'paste'",
        "ALTER TABLE documents ADD COLUMN file_name VARCHAR(255)",
        "ALTER TABLE analyses ADD COLUMN metrics TEXT",
        "ALTER TABLE chat_messages ADD COLUMN rag_chunks_used INTEGER",
    ]
    for stmt in migrations:
        try:
            await conn.execute(text(stmt))
        except Exception:
            pass


async def init_db() -> None:
    from app import models  # noqa: F401

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        await _migrate(conn)
