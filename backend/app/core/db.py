from typing import AsyncGenerator

from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncEngine, AsyncSession, AsyncAttrs
from sqlalchemy.orm import DeclarativeBase

from backend.app.core.config import settings


class Base(AsyncAttrs, DeclarativeBase):
    __abstract__ = True

def create_engine(db_url: str) -> AsyncEngine:
    return create_async_engine(db_url, echo=True, pool_size=5, max_overflow=10)

def create_session_pool(engine):
    return async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

engine = create_engine(settings.SQLALCHEMY_DATABASE_URI)

async def get_db() -> AsyncGenerator[AsyncSession, None]:
    session_pool = create_session_pool(engine)
    async with session_pool() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()

