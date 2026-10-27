import logging
import uuid
from contextlib import aclosing

from fastapi import Request
from redis.asyncio import Redis
from starlette.middleware.base import RequestResponseEndpoint
from starlette.responses import JSONResponse, Response

logger = logging.getLogger(__name__)


async def check_rate_limit(conn: Redis, key: str, limit: int, window: int = 60) -> bool:
    count = await conn.incr(key)
    if count == 1:
        await conn.expire(key, window)
    return count > limit

async def generate_request_id(
        request: Request,
        call_next: RequestResponseEndpoint,
) -> Response:
    request_id = str(uuid.uuid4())
    request.state.request_id = request_id
    try:
        response = await call_next(request)
        response.headers["X-Request-ID"] = request_id

        if 400 <= response.status_code < 600:
            logger.error(
                f'Запрос завершился ошибкой: status={response.status_code}'
                f' request_id={request.state.request_id}'
            )
    except Exception:
        logger.error(f'Запрос завершился ошибкой: status=500 request_id={request_id}')
        return JSONResponse(
            status_code=500,
            content={'detail': 'Internal Server Error'},
            headers={"X-Request-ID": request_id},
        )

    return response


async def rate_limit_middleware(
    request: Request, call_next: RequestResponseEndpoint
) -> Response:
    client = request.scope.get('client')
    client_ip: str = client[0] if client else 'unknown'

    if request.url.path not in ('/health', '/ready'):
        redis_connection = request.app.state.redis_provider
        async with aclosing(redis_connection()) as connections:
            async for conn in connections:
                if request.url.path in (
                    '/auth/login',
                    '/auth/register',
                ):
                    exceeded = await check_rate_limit(
                        conn, f'ratelimit:auth:{client_ip}', limit=5
                    )
                else:
                    exceeded = await check_rate_limit(
                        conn, f'ratelimit:global:{client_ip}', limit=60
                    )
                if exceeded:
                    return JSONResponse(
                        status_code=429, content={'detail': 'Too Many Requests'}
                    )

    response = await call_next(request)

    return response
