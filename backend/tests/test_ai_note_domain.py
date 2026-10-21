from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock

import pytest
from sqlalchemy import delete

from backend.app.models.database_models import Deal

from backend.app.working_llm.llm_classes import ExtractedDealInfo


@pytest.mark.parametrize('scenario', ['create', 'update'])
async def test_ai_waits_without_transaction_and_invalidates_after_commit(
        scenario, client, active_user, monkeypatch, redis_session, session_pool):
    from backend.app.api.routes import clients as routes

    headers = active_user[0]
    me = await client.get('/auth/me', headers=headers)
    assert me.status_code == 200
    customer = await client.post('/clients', headers=headers, json={
        'client_name': 'AI transaction client',
    })
    assert customer.status_code == 201
    client_id = customer.json()['id']
    original_id = None
    if scenario == 'update':
        created = await client.post('/deals', headers=headers, json={
            'name': 'Original', 'amount': '100.00', 'client_id': client_id,
        })
        assert created.status_code == 201
        original_id = created.json()['id']
    key = f"dashboard:{me.json()['id']}"
    other_key = 'dashboard:unrelated-user'
    await redis_session.set(key, 'old summary')
    await redis_session.set(other_key, 'other summary')
    original_read = routes.get_deals_by_client_id
    captured = {}

    async def capture_session(**kwargs):
        captured['session'] = kwargs['session']
        return await original_read(**kwargs)

    async def provider(**kwargs):
        assert not captured['session'].in_transaction(), 'AI waits inside a DB transaction'
        assert await redis_session.get(key) == 'old summary'
        return ExtractedDealInfo(name='Saved proposal', amount='250.00',
                                 matched_index=0 if scenario == 'update' else None)

    original_delete = redis_session.delete
    deletion_seen = []

    async def verify_commit(*keys):
        from sqlalchemy import select
        if key in keys:
            async with session_pool() as session:
                saved = await session.scalar(select(Deal).where(
                    Deal.client_id == client_id, Deal.name == 'Saved proposal'))
                assert saved is not None, 'Cache invalidated before commit'
                assert str(saved.amount) == '250.00'
                if original_id is not None:
                    assert saved.id == original_id
            deletion_seen.append(key)
        return await original_delete(*keys)

    monkeypatch.setattr(routes, 'get_deals_by_client_id', capture_session)
    monkeypatch.setattr(routes, 'note_formatter', provider)
    monkeypatch.setattr(redis_session, 'delete', verify_commit)
    response = await client.post(
        f'/clients/{client_id}/notes', headers=headers,
        json='Согласовали стоимость разработки сайта в размере 250 долларов.',
    )
    assert response.status_code == 201, response.text
    assert deletion_seen == [key]
    assert await redis_session.get(key) is None
    assert await redis_session.get(other_key) == 'other summary'


async def test_ai_cannot_reduce_deal_below_issued_amount(
        client, active_user, monkeypatch, redis_session):
    headers = active_user[0]
    me = await client.get('/auth/me', headers=headers)
    assert me.status_code == 200
    customer = await client.post('/clients', headers=headers, json={
        'client_name': 'AI domain client',
    })
    assert customer.status_code == 201, customer.text
    client_id = customer.json()['id']
    created = await client.post('/deals', headers=headers, json={
        'name': 'Website', 'amount': '100.00', 'client_id': client_id,
    })
    assert created.status_code == 201, created.text
    deal_id = created.json()['id']
    invoice = await client.post('/invoices', headers=headers, json={
        'deal_id': deal_id, 'label': 'First payment', 'amount': '80.00',
        'due_date': (datetime.now(timezone.utc).date() + timedelta(days=30)).isoformat(),
    })
    assert invoice.status_code == 201, invoice.text
    issued = await client.post(f"/invoices/{invoice.json()['id']}/issue", headers=headers)
    assert issued.status_code == 200, issued.text
    before = await client.get(f'/deals/{deal_id}', headers=headers)
    assert before.status_code == 200
    key = f"dashboard:{me.json()['id']}"
    await redis_session.set(key, 'cached summary')
    formatter = AsyncMock(return_value=ExtractedDealInfo(
        matched_index=0, name='Changed name', amount='50.00',
    ))
    monkeypatch.setattr('backend.app.api.routes.clients.note_formatter', formatter)
    response = await client.post(
        f'/clients/{client_id}/notes', headers=headers,
        json='Договорились уменьшить стоимость разработки сайта до 50 долларов.',
    )
    assert response.status_code == 409, response.text
    assert isinstance(response.json()['detail'], str)
    formatter.assert_awaited_once()
    after = await client.get(f'/deals/{deal_id}', headers=headers)
    assert after.status_code == 200
    assert after.json() == before.json()
    assert await redis_session.get(key) == 'cached summary'


async def test_deal_deleted_during_ai_returns_404(
        client, active_user, monkeypatch, redis_session, session_pool):
    headers = active_user[0]
    me = await client.get('/auth/me', headers=headers)
    assert me.status_code == 200
    customer = await client.post('/clients', headers=headers, json={
        'client_name': 'Concurrent deletion client',
    })
    assert customer.status_code == 201
    client_id = customer.json()['id']
    created = await client.post('/deals', headers=headers, json={
        'name': 'Removed deal', 'amount': '100.00', 'client_id': client_id,
    })
    assert created.status_code == 201
    deal_id = created.json()['id']
    key = f"dashboard:{me.json()['id']}"
    await redis_session.set(key, 'cached summary')

    async def delete_before_response(**kwargs):
        # Реальное удаление отдельной транзакцией между чтением и обновлением.
        async with session_pool() as session:
            async with session.begin():
                await session.execute(delete(Deal).where(Deal.id == deal_id))
        return ExtractedDealInfo(matched_index=0, amount='250.00')

    monkeypatch.setattr('backend.app.api.routes.clients.note_formatter', delete_before_response)
    response = await client.post(
        f'/clients/{client_id}/notes', headers=headers,
        json='Обсудили изменение стоимости существующей сделки до 250 долларов.',
    )
    assert response.status_code == 404, response.text
    assert response.json() == {'detail': 'Deal not found'}
    assert await redis_session.get(key) == 'cached summary'
    async with session_pool() as session:
        assert await session.get(Deal, deal_id) is None
