from unittest.mock import AsyncMock
from types import SimpleNamespace
import asyncio

import pytest

from sqlalchemy import select

from backend.app.models.database_models import Deal
from google.genai.errors import APIError
from backend.app.working_llm import json_format


@pytest.mark.parametrize('scenario', ['raised_timeout', 'slow_call'])
async def test_ai_timeout_returns_504_without_changes(
        scenario,
        client, active_user, monkeypatch, redis_session, session_pool):
    headers = active_user[0]
    me = await client.get('/auth/me', headers=headers)
    assert me.status_code == 200
    created = await client.post('/clients', headers=headers, json={
        'client_name': 'Timeout client',
    })
    assert created.status_code == 201
    client_id = created.json()['id']
    key = f"dashboard:{me.json()['id']}"
    await redis_session.set(key, 'cached summary')
    cancelled = asyncio.Event()

    async def slow_call(**kwargs):
        try:
            await asyncio.Event().wait()
        finally:
            cancelled.set()

    monkeypatch.setattr('backend.app.api.routes.clients.settings.GENERAL_TIMEOUT', 0.02)
    # Здесь проверяем отмену AI; реальный Redis покрыт test_ai_rate_limit.py.
    monkeypatch.setattr('backend.app.api.routes.clients.check_rate_limit',
                        AsyncMock(return_value=False))
    formatter = AsyncMock(side_effect=slow_call if scenario == 'slow_call'
                          else TimeoutError('private-provider-details'))
    monkeypatch.setattr('backend.app.api.routes.clients.note_formatter', formatter)
    response = await client.post(
        f'/clients/{client_id}/notes', headers=headers,
        json='Обсудили разработку сайта и стоимость выполнения работ.',
    )
    assert response.status_code == 504, response.text
    assert response.json()['detail']
    assert 'private-provider-details' not in response.text
    formatter.assert_awaited_once()
    if scenario == 'slow_call':
        assert cancelled.is_set()
    assert await redis_session.get(key) == 'cached summary'
    async with session_pool() as session:
        assert await session.scalar(select(Deal).where(Deal.client_id == client_id)) is None


async def test_total_timeout_cancels_retry_backoff(
        client, active_user, monkeypatch, redis_session, session_pool):
    headers = active_user[0]
    me = await client.get('/auth/me', headers=headers)
    assert me.status_code == 200
    created = await client.post('/clients', headers=headers, json={
        'client_name': 'Retry timeout client',
    })
    assert created.status_code == 201
    client_id = created.json()['id']
    cache_key = f"dashboard:{me.json()['id']}"
    await redis_session.set(cache_key, 'cached summary')
    call = AsyncMock(side_effect=APIError(503, {
        'error': {'message': 'private-provider-detail'},
    }))
    monkeypatch.setattr(json_format, 'client', SimpleNamespace(
        aio=SimpleNamespace(interactions=SimpleNamespace(create=call))))
    entered_backoff = asyncio.Event()
    cancelled_backoff = asyncio.Event()

    async def observed_sleep(delay):
        entered_backoff.set()
        try:
            await asyncio.sleep(delay)
        except asyncio.CancelledError:
            cancelled_backoff.set()
            raise

    # Сохраняем настоящие правила повторов и длительность паузы Tenacity.
    monkeypatch.setattr(json_format.note_formatter.retry, 'sleep', observed_sleep)
    monkeypatch.setattr('backend.app.api.routes.clients.settings.GENERAL_TIMEOUT', 0.1)
    response = await client.post(
        f'/clients/{client_id}/notes', headers=headers,
        json='Обсудили разработку сайта и стоимость выполнения работ.',
    )
    assert response.status_code == 504, response.text
    assert 'private-provider-detail' not in response.text
    assert entered_backoff.is_set()
    assert cancelled_backoff.is_set()
    call.assert_awaited_once()
    assert await redis_session.get(f"ratelimit:ai:{me.json()['id']}") == '1'
    assert await redis_session.get(cache_key) == 'cached summary'
    async with session_pool() as session:
        assert await session.scalar(select(Deal).where(Deal.client_id == client_id)) is None
