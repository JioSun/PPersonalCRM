import logging

from fastapi import FastAPI

from backend.app.api.routes import users, clients, deals, invoices, dashboards, job
from backend.app.logger import setup_logging
from backend.app.middlewares.rate_limiting import rate_limit_middleware

setup_logging()

logger = logging.getLogger(__name__)

app = FastAPI(title="Secure API")
logger.info("App init")

app.include_router(
    users.router,
)
logger.debug("Users router init")

app.include_router(
    clients.router,
)
logger.debug("Clients router init")

app.include_router(
    deals.router,
)

logger.debug("Deals router init")

app.include_router(
    invoices.router,
)

app.include_router(
    dashboards.router,
)

app.include_router(
    job.router,
)
logger.debug("Invoice router init")

#app.middleware("http://localhost")(rate_limit_middleware)
@app.get("/")
async def greetings():
    logger.info("Greetings router init")
    return {"greetings": "Hello World"}

@app.get("/health")
async def health():
    logger.info("Health router init")
    return True

