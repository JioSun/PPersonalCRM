import os


os.environ["POSTGRES_DB"] = "personalcrm_test"
os.environ['REDIS_DB'] = "5"


import pytest_asyncio
import pytest
from alembic import command
from alembic.config import Config
from httpx import ASGITransport, AsyncClient
from redis import asyncio as redis
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine, AsyncEngine, AsyncConnection
from typing_extensions import AsyncGenerator
from redis.asyncio import Redis, ConnectionPool
from backend.app.core.config import settings
from backend.app.core.db import get_db
from backend.app.core.redis_py import get_redis
from backend.app.models.database_models import Base
from pydantic import RedisDsn, TypeAdapter, PostgresDsn

def validate_test_redis(redis_url: str) -> None:
    adapter = TypeAdapter(RedisDsn)
    url = adapter.validate_python(redis_url)
    if url.host != 'localhost':
        raise RuntimeError('Тест не может быть пройден по причине несовпадения хоста')
    if url.port != 6379:
        raise RuntimeError('Тест не может быть пройден по причине несовпадения порта')
    if url.path != '/5':
        raise RuntimeError('Тест не может быть пройден так как по причине несовпадения номера тестовой бд')

def validate_test_database(db_url: str) -> None:
    adapter = TypeAdapter(PostgresDsn)
    url = adapter.validate_python(db_url)
    hosts = url.hosts()
    for host in hosts:
        if url.path != '/personalcrm_test':
            raise RuntimeError('Тест не может быть пройден по причине несовпадения имён бд')
        if host.get('host') != 'localhost':
            raise RuntimeError('Тест не может быть пройден по причине несовпадения хоста')
        if host.get('port') != 5432:
            raise RuntimeError('Тест не может быть пройден по причине несовпадения порта')

async def truncate_table(session: AsyncConnection) -> None:
    tables = ', '.join(table.name for table in Base.metadata.tables.values())
    await session.execute(text(f"TRUNCATE {tables}"))

def get_engine() -> AsyncEngine:
    TEST_DATABASE_URL = settings.SQLALCHEMY_DATABASE_URI
    validate_test_database(TEST_DATABASE_URL)
    return create_async_engine(TEST_DATABASE_URL)

def get_redis_connection_pool():
    TEST_REDIS_URL = settings.REDIS_DATABASE_URL
    validate_test_redis(TEST_REDIS_URL)
    return ConnectionPool.from_url(TEST_REDIS_URL, decode_responses=True)

@pytest.fixture(scope='session', autouse=True)
def upgrade_migration():
    validate_test_database(settings.SQLALCHEMY_DATABASE_URI)
    command.upgrade(Config("alembic.ini"), "head")

@pytest_asyncio.fixture(scope='function')
async def clean_tables():
    engine = get_engine()
    try:
        async with engine.begin() as conn:
            await truncate_table(conn)
        try:
            yield
        finally:
            async with engine.begin() as conn:
                await truncate_table(conn)
    finally:
        await engine.dispose()

@pytest_asyncio.fixture(scope='function')
async def clean_redis():
    connection_pool = get_redis_connection_pool()
    try:
        async with Redis(connection_pool=connection_pool) as conn:
            await conn.flushdb()
        try:
            yield
        finally:
            async with Redis(connection_pool=connection_pool) as conn:
                await conn.flushdb()
    finally:
        await connection_pool.aclose()

@pytest_asyncio.fixture(scope="session")
async def session_pool():
    engine = get_engine()
    session_pool = async_sessionmaker(engine, expire_on_commit=False)
    try:
        yield session_pool
    finally:
        await engine.dispose()

@pytest_asyncio.fixture(scope="function", autouse=True)
async def async_session(clean_tables, session_pool) -> AsyncGenerator[AsyncSession, None]:
    validate_test_database(settings.SQLALCHEMY_DATABASE_URI)
    async with session_pool() as session:
        yield session

@pytest_asyncio.fixture(scope="function", autouse=True)
async def redis_session(clean_redis):
    validate_test_redis(settings.REDIS_DATABASE_URL)
    connection_pool = get_redis_connection_pool()
    try:

        async with redis.Redis(connection_pool=connection_pool) as conn:
            yield conn
    finally:
        await connection_pool.aclose()



@pytest_asyncio.fixture
async def client(async_session, redis_session):
    async def async_overrides_session():
        yield async_session

    async def async_overrides_redis_session():
        yield redis_session

    from backend.app.main import app
    previous_provider = app.state.redis_provider
    previous_overrides = app.dependency_overrides.copy()

    try:
        app.state.redis_provider = async_overrides_redis_session
        app.dependency_overrides[get_db] = async_overrides_session
        app.dependency_overrides[get_redis] = async_overrides_redis_session
        transport = ASGITransport(app)
        async with AsyncClient(transport=transport, base_url='http://test') as ac:
            yield ac
    finally:
        app.state.redis_provider = previous_provider
        app.dependency_overrides.clear()
        app.dependency_overrides.update(previous_overrides)


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
    registration = await client.post("/auth/register", json=auth_user_json())
    assert registration.status_code == 200, registration.text
    response = await client.post("/auth/login", data=login_user_json())
    assert response.status_code == 200, response.text
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
    registration = await client.post("/auth/register", json=other_auth_user_json())
    assert registration.status_code == 200, registration.text
    response = await client.post("/auth/login", data=other_login_user_json())
    assert response.status_code == 200, response.text
    headers = {"Authorization": f"Bearer {response.json()['access_token']}"}
    return headers

@pytest_asyncio.fixture
async def bother_user(active_user, other_active_user):
    return active_user[0], other_active_user

def client_a():
    client_json = {
        "client_name": "JoeA",
        "organization": "JoeCorpA",
        "email": "joecorpA@example.com",
        "client_status": "lead",
    }
    return client_json

def client_b():
    client_json = {
        "client_name": "JoeB",
        "organization": "JoeCorpB",
        "email": "joecorpB@example.com",
        "client_status": "lead",
    }
    return client_json

@pytest_asyncio.fixture
async def users_with_created_clients(client, bother_user):
    create_clientA = await client.post('/clients', json=client_a(), headers=bother_user[0])
    create_clientB = await client.post('/clients', json=client_b(), headers=bother_user[1])

    assert create_clientA.status_code == 200, create_clientA.text
    assert create_clientB.status_code == 200, create_clientB.text

    return create_clientA, create_clientB