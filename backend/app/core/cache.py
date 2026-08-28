from redis import Redis

async def invalidate_dashboard(redis: Redis, user_id: str) -> None:
    await redis.delete(f"dashboard:{user_id}")