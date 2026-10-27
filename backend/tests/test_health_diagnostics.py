import asyncio
import logging
import time
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from redis.exceptions import ConnectionError as RedisConnectionError
from redis.exceptions import TimeoutError as RedisTimeoutError
from sqlalchemy import create_engine, text
from sqlalchemy.exc import DBAPIError

from backend.app import main
from backend.app.core.db import get_db
from backend.app.core.redis_py import get_redis


@pytest_asyncio.fixture
async def diagnostics(monkeypatch):
    redis = MagicMock()
    redis.ping = AsyncMock(return_value=True)
    redis.incr = AsyncMock(return_value=61)
    session = MagicMock()
    result = MagicMock()
    result.scalar.return_value = 1
    session.execute = AsyncMock(return_value=result)

    async def db_dependency():
        yield session

    async def redis_dependency():
        yield redis

    previous = main.app.dependency_overrides.copy()
    main.app.dependency_overrides[get_db] = db_dependency
    main.app.dependency_overrides[get_redis] = redis_dependency
    monkeypatch.setattr(main.app.state, 'redis_provider', redis_dependency)
    try:
        async with AsyncClient(
            transport=ASGITransport(main.app), base_url='http://test'
        ) as client:
            yield client, redis, session
    finally:
        main.app.dependency_overrides.clear()
        main.app.dependency_overrides.update(previous)


async def test_health_and_ready_bypass_exhausted_limit(diagnostics):
    client, redis, session = diagnostics
    assert (await client.get('/')).status_code == 429
    for _ in range(65):
        assert (await client.get('/health')).status_code == 200
    response = await client.get('/ready')
    assert response.status_code == 200
    assert response.json() == {'status': 'ok'}
    redis.incr.assert_awaited_once()
    redis.ping.assert_awaited_once()
    session.execute.assert_awaited_once()


async def test_liveness_never_opens_redis(diagnostics, monkeypatch):
    client, redis, session = diagnostics

    def unavailable():
        raise AssertionError('health must not acquire Redis')

    monkeypatch.setattr(main.app.state, 'redis_provider', unavailable)
    assert (await client.get('/health')).status_code == 200
    redis.ping.assert_not_awaited()
    session.execute.assert_not_awaited()


@pytest.mark.parametrize(
    'target,error',
    [
        ('redis', RedisConnectionError('synthetic-secret')),
        ('redis', RedisTimeoutError('synthetic-secret')),
        ('db', DBAPIError('SELECT 1', {}, Exception('synthetic-secret'))),
        ('db', ConnectionRefusedError('synthetic-secret')),
        ('db', TimeoutError('synthetic-secret')),
    ],
)
async def test_readiness_dependency_errors(diagnostics, caplog, target, error):
    client, redis, session = diagnostics
    operation = redis.ping if target == 'redis' else session.execute
    operation.side_effect = error
    with caplog.at_level(logging.ERROR):
        response = await client.get('/ready')
    assert response.status_code == 503
    assert response.json() == {'detail': {'status': 'unavailable'}}
    request_id = response.headers['X-Request-ID']
    assert f'status=503 request_id={request_id}' in caplog.text
    assert 'synthetic-secret' not in response.text + caplog.text


@pytest.mark.parametrize('target', ['redis', 'db'])
async def test_readiness_timeout(diagnostics, target):
    client, redis, session = diagnostics

    async def slow(*args):
        await asyncio.sleep(10)

    operation = redis.ping if target == 'redis' else session.execute
    operation.side_effect = slow
    started = time.monotonic()
    response = await client.get('/ready')
    elapsed = time.monotonic() - started
    assert response.status_code == 503
    # Allow scheduler overhead; the configured timeout itself is two seconds.
    assert 1.8 <= elapsed < 3.5


@pytest.mark.parametrize('target', ['redis', 'db'])
async def test_readiness_unexpected_probe_result(diagnostics, target):
    client, redis, session = diagnostics
    if target == 'redis':
        redis.ping.return_value = False
    else:
        session.execute.return_value.scalar.return_value = 0
    assert (await client.get('/ready')).status_code == 503


async def test_ids_are_server_generated_and_distinct(diagnostics):
    client, _, _ = diagnostics
    responses = await asyncio.gather(
        *(
            client.get('/health', headers={'X-Request-ID': 'client-id'})
            for _ in range(8)
        )
    )
    ids = [response.headers['X-Request-ID'] for response in responses]
    assert len(set(ids)) == 8
    assert 'client-id' not in ids


async def test_limiter_error_log_matches_response(diagnostics, caplog):
    client, _, _ = diagnostics
    with caplog.at_level(logging.ERROR):
        response = await client.get('/')
    assert response.status_code == 429
    assert f'status=429 request_id={response.headers["X-Request-ID"]}' in caplog.text


async def test_unexpected_error_is_safe(diagnostics, caplog):
    client, redis, _ = diagnostics
    redis.ping.side_effect = ValueError('secret-note-password-jwt-api-key')
    with caplog.at_level(logging.ERROR):
        response = await client.get('/ready')
    assert response.status_code == 500
    assert response.json() == {'detail': 'Internal Server Error'}
    assert f'status=500 request_id={response.headers["X-Request-ID"]}' in caplog.text
    assert 'secret-note-password-jwt-api-key' not in response.text + caplog.text


async def test_cancellation_is_not_converted_to_http_error(diagnostics):
    client, redis, _ = diagnostics
    started = asyncio.Event()

    async def wait_for_cancellation():
        started.set()
        await asyncio.Event().wait()

    redis.ping.side_effect = wait_for_cancellation
    task = asyncio.create_task(client.get('/ready'))
    await asyncio.wait_for(started.wait(), timeout=3)
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task


@pytest.mark.parametrize('failure', [None, 'body', 'postgres', 'redis'])
async def test_lifespan_attempts_both_cleanups(monkeypatch, failure):
    engine = SimpleNamespace(dispose=AsyncMock())
    pool = SimpleNamespace(disconnect=AsyncMock())
    monkeypatch.setattr(main, 'engine', engine)
    monkeypatch.setattr(main, 'redis_pool', pool)
    if failure == 'postgres':
        engine.dispose.side_effect = RuntimeError('synthetic cleanup error')
    if failure == 'redis':
        pool.disconnect.side_effect = RuntimeError('synthetic cleanup error')

    async def run_lifespan():
        async with main.app.router.lifespan_context(main.app):
            engine.dispose.assert_not_awaited()
            pool.disconnect.assert_not_awaited()
            if failure == 'body':
                raise RuntimeError('synthetic context error')

    if failure:
        with pytest.raises(RuntimeError):
            await run_lifespan()
    else:
        await run_lifespan()
    engine.dispose.assert_awaited_once()
    pool.disconnect.assert_awaited_once()


def test_sql_parameter_not_in_query_or_exception_logs(caplog):
    marker = 'SYNTHETIC_PRIVATE_NOTE_83'
    engine = create_engine(
        'sqlite://',
        echo=main.engine.echo,
        hide_parameters=main.engine.sync_engine.hide_parameters,
    )
    try:
        with caplog.at_level(logging.INFO, logger='sqlalchemy.engine'):
            with engine.connect() as conn:
                assert (
                    conn.execute(text('SELECT :note'), {'note': marker}).scalar()
                    == marker
                )
                try:
                    conn.execute(
                        text('SELECT * FROM absent_table WHERE note = :note'),
                        {'note': marker},
                    )
                except DBAPIError as exc:
                    assert marker not in str(exc)
                    logging.getLogger(__name__).exception('Synthetic SQL failure')
                else:
                    pytest.fail('Expected SQL error')
        assert 'SELECT' in caplog.text
        assert marker not in caplog.text
    finally:
        engine.dispose()
