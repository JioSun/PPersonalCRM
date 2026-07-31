import logging

from fastapi import FastAPI

from backend.app.api.routes import users, clients
from backend.app.logger import setup_logging

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

@app.get("/")
async def greetings():
    logger.info("Greetings router init")
    return {"greetings": "Hello World"}

@app.get("/health")
async def health():
    logger.info("Health router init")
    return True

