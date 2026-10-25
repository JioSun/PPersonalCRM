import logging

from fastapi import FastAPI

from .api.routes import clients, dashboards, deals, invoices, pay, users
from .core.redis_py import get_redis
from .logger import setup_logging
from .middlewares.rate_limiting import rate_limit_middleware

setup_logging()

logger = logging.getLogger(__name__)

app = FastAPI(title='Secure API')

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


@app.get('/')
async def greetings():
    logger.info('Greetings router init')
    return {'greetings': 'Hello World'}


@app.get('/health')
async def health():
    logger.info('Health router init')
    return {'status': 'ok'}
