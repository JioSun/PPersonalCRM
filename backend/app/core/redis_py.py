import redis
from typing import Generator
from backend.app.core.config import settings

def create_redis_pool(host=settings.REDIS_HOST, port=settings.REDIS_PORT):
    return redis.ConnectionPool(host=host, port=port, decode_responses=True)

async def get_redis() -> Generator[redis.Redis, None, None]:
    client = redis.Redis(connection_pool=create_redis_pool())
    try:
        yield client
    finally:
        client.close()