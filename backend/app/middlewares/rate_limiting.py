from fastapi import Request
from redis.asyncio import Redis
from starlette.middleware.base import RequestResponseEndpoint
from starlette.responses import JSONResponse, Response

from backend.app.core.redis_py import get_redis


async def check_rate_limit(conn: Redis, key: str, limit: int, window: int = 60) -> bool:
    count = await conn.incr(key)
    if count == 1:
        await conn.expire(key, window)
    return count > limit


async def rate_limit_middleware(
    request: Request, call_next: RequestResponseEndpoint
) -> Response:
    client = request.scope.get('client')
    client_ip: str = client[0] if client else 'unknown'

    async for conn in get_redis():
        if request.url.path in ('/auth/login', '/auth/register'):
            exceeded = await check_rate_limit(
                conn, f'ratelimit:auth:{client_ip}', limit=5
            )
        else:
            exceeded = await check_rate_limit(conn, f'ratelimit:global:{client_ip}', limit=60)
        if exceeded:
            return JSONResponse(
                status_code=429, content={'detail': 'Too Many Requests'}
            )

    return await call_next(request)
