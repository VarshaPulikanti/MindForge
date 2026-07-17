from collections.abc import AsyncGenerator

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from app.config import settings

_db_url = settings.async_database_url
engine = create_async_engine(
    _db_url,
    echo=False,
    connect_args=settings.database_connect_args,
    pool_pre_ping=True,
)
async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    from fastapi import HTTPException

    try:
        async with async_session() as session:
            yield session
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Database connection failed: {exc.__class__.__name__}: {exc}",
        ) from exc


async def _migrate() -> None:
    """Run each DDL in its own transaction.

    On PostgreSQL, one failed statement aborts the whole transaction. If migrations
    shared a transaction with create_all, a duplicate-column error would roll back
    newly created tables (e.g. users).
    """
    migrations = [
        "ALTER TABLE documents ADD COLUMN source_type VARCHAR(16) DEFAULT 'paste'",
        "ALTER TABLE documents ADD COLUMN file_name VARCHAR(255)",
        "ALTER TABLE analyses ADD COLUMN metrics TEXT",
        "ALTER TABLE chat_messages ADD COLUMN rag_chunks_used INTEGER",
        "ALTER TABLE documents ADD COLUMN user_id INTEGER REFERENCES users(id)",
    ]
    for stmt in migrations:
        try:
            async with engine.begin() as conn:
                await conn.execute(text(stmt))
        except Exception:
            pass


async def _sqlite_pragmas(conn) -> None:
    if "sqlite" not in _db_url:
        return
    await conn.execute(text("PRAGMA journal_mode=WAL"))
    await conn.execute(text("PRAGMA synchronous=NORMAL"))
    await conn.execute(text("PRAGMA busy_timeout=30000"))


async def init_db() -> None:
    from app import models  # noqa: F401

    async with engine.begin() as conn:
        await _sqlite_pragmas(conn)
        await conn.run_sync(Base.metadata.create_all)

    await _migrate()
