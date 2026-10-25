from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from google.genai.errors import APIError
from tenacity import wait_none

from ..app.working_llm import json_format


@pytest.mark.parametrize(
    'code, attempts',
    [
        (429, 3),
        (500, 3),
        (503, 3),
        (400, 1),
        (401, 1),
        (403, 1),
    ],
)
async def test_provider_retry_policy(code, attempts, monkeypatch):
    error = APIError(code, {'error': {'message': 'private-provider-detail'}})
    call = AsyncMock(side_effect=error)
    monkeypatch.setattr(
        json_format,
        'client',
        SimpleNamespace(aio=SimpleNamespace(interactions=SimpleNamespace(create=call))),
    )
    monkeypatch.setattr(json_format.note_formatter.retry, 'wait', wait_none())
    with pytest.raises(APIError) as caught:
        await json_format.note_formatter('Test note', '')
    assert caught.value is error
    assert call.await_count == attempts


async def test_provider_succeeds_on_retry(monkeypatch):
    call = AsyncMock(
        side_effect=[
            APIError(503, {'error': {'message': 'temporary'}}),
            SimpleNamespace(output_text='{"name":"Website","amount":"100.00"}'),
        ]
    )
    monkeypatch.setattr(
        json_format,
        'client',
        SimpleNamespace(aio=SimpleNamespace(interactions=SimpleNamespace(create=call))),
    )
    monkeypatch.setattr(json_format.note_formatter.retry, 'wait', wait_none())
    result = await json_format.note_formatter('Test note', '')
    assert result.name == 'Website'
    assert call.await_count == 2


async def test_exhausted_provider_error_returns_safe_502(
    client, active_user, monkeypatch, redis_session, session_pool
):
    from sqlalchemy import select

    from ..app.models.database_models import Deal

    headers = active_user[0]
    me = await client.get('/auth/me', headers=headers)
    assert me.status_code == 200
    customer = await client.post(
        '/clients',
        headers=headers,
        json={
            'client_name': 'Provider failure client',
        },
    )
    assert customer.status_code == 201
    client_id = customer.json()['id']
    key = f'dashboard:{me.json()["id"]}'
    await redis_session.set(key, 'cached summary')
    call = AsyncMock(
        side_effect=APIError(
            503,
            {
                'error': {'message': 'private-provider-detail fake-key'},
            },
        )
    )
    monkeypatch.setattr(
        json_format,
        'client',
        SimpleNamespace(aio=SimpleNamespace(interactions=SimpleNamespace(create=call))),
    )
    monkeypatch.setattr(json_format.note_formatter.retry, 'wait', wait_none())
    response = await client.post(
        f'/clients/{client_id}/notes',
        headers=headers,
        json='Обсудили разработку сайта и стоимость выполнения работ.',
    )
    assert response.status_code == 502, response.text
    assert response.json()['detail']
    assert 'private-provider-detail' not in response.text
    assert 'fake-key' not in response.text
    assert call.await_count == 3
    assert await redis_session.get(key) == 'cached summary'
    async with session_pool() as session:
        assert (
            await session.scalar(select(Deal).where(Deal.client_id == client_id))
            is None
        )
