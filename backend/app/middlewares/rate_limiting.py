from fastapi import Request
from redis import Redis
from starlette.responses import JSONResponse

from backend.app.core.redis_py import get_redis


async def check_rate_limit(conn, key: str, limit: int, window: int = 60) -> bool:
    count = await conn.incr(key)
    if count == 1:
        await conn.expire(key, window)
    return count > limit

async def rate_limit_middleware(request: Request, call_next):
    client_ip = request.client.host
    async for conn in get_redis():
        if request.url.path in ("/login", "/register"):
            exceeded = await check_rate_limit(conn, f"ratelimit:auth:{client_ip}", limit=5)
        else:
            exceeded = await check_rate_limit(conn, f"ratelimit:{client_ip}", limit=60)
        if exceeded:
            return JSONResponse(status_code=429, content={"detail": "Too Many Requests"})
        break
    return await call_next(request)