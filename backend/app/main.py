import asyncio
import logging
from contextlib import asynccontextmanager
from typing import Any, AsyncGenerator

import redis
from fastapi import Depends, FastAPI, HTTPException, status
from redis.asyncio import Redis
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.ext.asyncio import AsyncSession

from .api.routes import clients, dashboards, deals, invoices, pay, users
from .core.db import engine, get_db
from .core.redis_py import get_redis, redis_pool
from .logger import setup_logging
from .middlewares.rate_limiting import generate_request_id, rate_limit_middleware

setup_logging()

logger = logging.getLogger(__name__)

@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    try:
        yield
    finally:
        try:
            await engine.dispose()
        finally:
            await redis_pool.disconnect()


app = FastAPI(title='Secure API', lifespan=lifespan)

app.state.redis_provider = get_redis

app.include_router(
    users.router,
)

app.include_router(
    clients.router,
)

app.include_router(
    deals.router,
)


app.include_router(
    invoices.router,
)

app.include_router(
    dashboards.router,
)

app.include_router(
    pay.router,
)

app.middleware('http')(rate_limit_middleware)
app.middleware('http')(generate_request_id)




@app.get('/')
async def greetings():
    logger.info('Greetings router init')
    return {'greetings': 'Hello World'}


@app.get('/health', status_code=status.HTTP_200_OK)
async def health():
    logger.info('Health router init')
    return {'status': 'ok'}

@app.get('/ready', status_code=status.HTTP_200_OK)
async def ready(
        conn: Redis = Depends(get_redis),
        session: AsyncSession = Depends(get_db, use_cache=False),
    ) -> Any:
    try:
        async with asyncio.timeout(2):
            life_redis = await conn.ping()
            if not life_redis:
                raise HTTPException(
                    status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                    detail={"status":'unavailable'}
                )

            async with session.begin():
                result = await session.execute(text("SELECT 1"))
                if result.scalar() !=  1:
                    raise HTTPException(
                        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                        detail={"status":'unavailable'}
                    )
    except (
            TimeoutError,
            DBAPIError,
            OSError,
            redis.exceptions.TimeoutError,
            redis.exceptions.ConnectionError
    ):
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={"status":'unavailable'}
        )
    return {"status": "ok"}