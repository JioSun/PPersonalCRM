import asyncio
from typing import AsyncGenerator

from redis import asyncio as redis

from backend.app.core.config import settings

redis_pool = redis.ConnectionPool.from_url(
    f"redis://{settings.REDIS_HOST}:{settings.REDIS_PORT}/{settings.REDIS_DB}",
    decode_responses=True,
)


async def get_redis() -> AsyncGenerator[redis.Redis, None]:
    async with redis.Redis(connection_pool=redis_pool) as conn:
        yield conn
