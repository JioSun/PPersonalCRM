import os

import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from typing_extensions import AsyncGenerator

from backend.app.core.db import get_db
from backend.app.core.redis_py import get_redis
from backend.app.models.database_models import Base

os.environ["POSTGRES_DB"] = "personalcrm_test"

from alembic import command
from alembic.config import Config
from redis import asyncio as redis

from backend.app.core.config import settings



@pytest_asyncio.fixture(scope="session", autouse=True)
def apply_migrations():
    command.upgrade(Config("alembic.ini"), "head")

@pytest_asyncio.fixture()
async def async_engine():
    TEST_DATABASE_URL = settings.SQLALCHEMY_DATABASE_URI

    engine = create_async_engine(TEST_DATABASE_URL)
    return engine

@pytest_asyncio.fixture
async def session_pool(async_engine):
    return async_sessionmaker(async_engine)

@pytest_asyncio.fixture(scope="function", autouse=True)
async def async_session(async_engine) -> AsyncGenerator[AsyncSession, None]:
    session_pool = async_sessionmaker(async_engine,  expire_on_commit=False)
    async with session_pool() as session:
        try:
            yield session
        finally:
            for table in reversed(Base.metadata.sorted_tables):
                await session.execute(text(f"TRUNCATE TABLE {table.name} RESTART IDENTITY CASCADE;"))
                await session.commit()
            await session.close()

@pytest_asyncio.fixture(scope="function", autouse=True)
async def redis_session():
    redis_pool = redis.ConnectionPool.from_url(
        f'redis://{settings.REDIS_HOST}:6379/0',
        decode_responses=True,
    )

    async with redis.Redis(connection_pool=redis_pool) as conn:
        try:
            yield conn
        finally:
            await conn.flushdb()
            await conn.aclose()


@pytest_asyncio.fixture
async def client(async_session, redis_session):
    def async_overrides_session():
        yield async_session

    def async_overrides_redis_session():
        yield redis_session

    from backend.app.main import app

    app.dependency_overrides[get_db] = async_overrides_session
    app.dependency_overrides[get_redis] = async_overrides_redis_session

    transport = ASGITransport(app)
    async with AsyncClient(transport=transport, base_url='http://test') as ac:
        yield ac

    app.dependency_overrides.clear()

def auth_user_json() -> dict:
    json = {
        "email": "testuser@xample.com",
        "full_name": "User Test",
        "username": "UTest",
        "password": "Kill2896"
    }
    return json

def login_user_json() -> dict:
    json = {
        "username": "testuser@xample.com",
        "password": "Kill2896"
    }

    return json

@pytest_asyncio.fixture
async def active_user(client):
    await client.post("/auth/register", json=auth_user_json())
    response = await client.post("/auth/login", data=login_user_json())
    headers = {"Authorization": f"Bearer {response.json()['access_token']}"}

    return headers, response

def other_auth_user_json() -> dict:
    json = {
        "email": "testuser1@xample.com",
        "full_name": "User Test1",
        "username": "UTest1",
        "password": "Kill2896"
    }
    return json

def other_login_user_json() -> dict:
    json = {
        "username": "testuser1@xample.com",
        "password": "Kill2896"
    }

    return json

@pytest_asyncio.fixture
async def other_active_user(client):
    await client.post("/auth/register", json=other_auth_user_json())
    response = await client.post("/auth/login", data=other_login_user_json())
    headers = {"Authorization": f"Bearer {response.json()['access_token']}"}

    return headers

