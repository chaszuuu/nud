# backend/db.py
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.pool import NullPool
from typing import AsyncGenerator

from config import settings

engine = create_async_engine(
    settings.DATABASE_URL,
    connect_args={
        "statement_cache_size": 0
    },
    echo=settings.APP_ENV == "development",  # logs SQL in dev only
    poolclass=NullPool,                       # safer for async, no connection leaks
)

AsyncSessionFactory = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,                   # prevents lazy load errors after commit
)


async def init_db():
    from models.base import Base
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with AsyncSessionFactory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()