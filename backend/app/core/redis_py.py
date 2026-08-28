from redis import asyncio as redis
from backend.app.core.config import settings
from typing import AsyncGenerator

import asyncio

redis_pool = redis.ConnectionPool.from_url(
    f"redis://{settings.REDIS_HOST}:{settings.REDIS_PORT}/{settings.REDIS_DB}",
    decode_responses=True,
)

async def get_redis() -> AsyncGenerator[redis.Redis, None]:
    async with redis.Redis(connection_pool=redis_pool) as conn:
            yield conn



async def main():
    async for conn in get_redis():
        result = await conn.ping()
        print(result)
        break

if '__main__' == __name__:
    asyncio.run(main())