from unittest.mock import AsyncMock
from types import SimpleNamespace

import pytest

from backend.app.working_llm.llm_classes import ExtractedDealInfo


@pytest.mark.parametrize('output_text', [
    'private-provider-output: this is not JSON',
    '{"name": "private-provider-output", "amount": "not-a-number"}',
    '{"name": "private-provider-output", "matched_index": "not-an-index"}',
    '{"name": "   ", "amount": "100.00"}',
    '{"name": "private-provider-output", "amount": "-1.00"}',
    '{"name": "private-provider-output", "amount": "1.234"}',
    '{"name": "private-provider-output", "amount": "10000000000.00"}',
    '{"name": "private-provider-output", "amount": "NaN"}',
    '{"name": "private-provider-output", "user_id": "untrusted-owner"}',
])
async def test_invalid_provider_json_returns_safe_error(
        output_text, client, active_user, monkeypatch, session_pool):
    from sqlalchemy import select
    from backend.app.models.database_models import Deal

    headers = active_user[0]
    customer = await client.post('/clients', headers=headers, json={
        'client_name': 'Malformed AI client',
    })
    assert customer.status_code == 201, customer.text
    client_id = customer.json()['id']
    # Подменён только SDK: настоящий note_formatter разбирает сырой ответ.
    provider_call = AsyncMock(return_value=SimpleNamespace(output_text=output_text))
    monkeypatch.setattr(
        'backend.app.working_llm.json_format.client',
        SimpleNamespace(aio=SimpleNamespace(
            interactions=SimpleNamespace(create=provider_call))),
    )
    response = await client.post(
        f'/clients/{client_id}/notes', headers=headers,
        json='Обсудили создание нового сайта и стоимость предстоящих работ.',
    )
    assert response.status_code == 502, response.text
    assert isinstance(response.json()['detail'], str)
    assert response.json()['detail'].strip()
    assert 'private-provider-output' not in response.text
    provider_call.assert_awaited_once()
    async with session_pool() as session:
        deals = await session.scalars(select(Deal).where(Deal.client_id == client_id))
        assert list(deals) == []


@pytest.mark.parametrize('scenario', ['empty_response', 'negative_index', 'outside_list', 'large_index'])
async def test_invalid_ai_selection_does_not_change_deal(
        scenario, client, active_user, monkeypatch):
    headers = active_user[0]
    customer = await client.post('/clients', headers=headers, json={
        'client_name': 'AI response client',
    })
    assert customer.status_code == 201, customer.text
    client_id = customer.json()['id']
    created = await client.post('/deals', headers=headers, json={
        'name': 'Original deal', 'amount': '100.00', 'client_id': client_id,
    })
    assert created.status_code == 201, created.text
    deal_id = created.json()['id']
    before = await client.get(f'/deals/{deal_id}', headers=headers)
    assert before.status_code == 200
    result = None if scenario == 'empty_response' else ExtractedDealInfo(
        name='Original deal', amount='999.00',
        matched_index={'negative_index': -1, 'outside_list': 1, 'large_index': 1000}[scenario],
    )
    formatter = AsyncMock(return_value=result)
    monkeypatch.setattr('backend.app.api.routes.clients.note_formatter', formatter)
    response = await client.post(
        f'/clients/{client_id}/notes', headers=headers,
        json='Обсудили изменение стоимости работ по существующей сделке.',
    )
    assert response.status_code == 502, response.text
    assert isinstance(response.json()['detail'], str)
    formatter.assert_awaited_once()
    after = await client.get(f'/deals/{deal_id}', headers=headers)
    assert after.status_code == 200
    assert after.json() == before.json()


@pytest.mark.parametrize('scenario', [
    'update_first', 'create_new', 'create_without_amount',
    'update_name_only', 'update_zero_amount', 'empty_update',
])
async def test_valid_ai_result_is_saved(scenario, client, active_user, monkeypatch):
    headers = active_user[0]
    customer = await client.post('/clients', headers=headers, json={
        'client_name': 'Valid AI client',
    })
    assert customer.status_code == 201, customer.text
    client_id = customer.json()['id']
    original_id = None
    is_update = scenario.startswith('update_') or scenario == 'empty_update'
    if is_update:
        created = await client.post('/deals', headers=headers, json={
            'name': 'Original deal', 'amount': '100.00', 'client_id': client_id,
            'deadline': '2030-06-01', 'notes': 'Keep existing notes',
        })
        assert created.status_code == 201, created.text
        original_id = created.json()['id']
    payload = {'name': '  Proposed deal  ', 'amount': '250.00',
               'matched_index': 0 if is_update else None}
    if scenario in ('create_without_amount', 'update_name_only'):
        payload.pop('amount')
    if scenario == 'update_zero_amount':
        payload.pop('name')
        payload['amount'] = '0.00'
    if scenario == 'empty_update':
        payload = {'matched_index': 0}
    formatter = AsyncMock(return_value=ExtractedDealInfo(**payload))
    monkeypatch.setattr('backend.app.api.routes.clients.note_formatter', formatter)
    note = 'Обсудили стоимость разработки сайта в размере 250 долларов.'
    response = await client.post(
        f'/clients/{client_id}/notes', headers=headers, json=note,
    )
    if scenario == 'empty_update':
        assert response.status_code == 502, response.text
        saved = await client.get(f'/deals/{original_id}', headers=headers)
        assert saved.status_code == 200
        for field in ('name', 'amount', 'deadline', 'notes', 'updated_at'):
            assert saved.json()[field] == created.json()[field]
        formatter.assert_awaited_once()
        return
    assert response.status_code == 201, response.text
    formatter.assert_awaited_once()
    saved_id = response.json()['id']
    saved = await client.get(f'/deals/{saved_id}', headers=headers)
    assert saved.status_code == 200, saved.text
    assert saved.json()['name'] == ('Original deal' if scenario == 'update_zero_amount' else 'Proposed deal')
    expected_amount = {'create_without_amount': '0.00',
                       'update_name_only': '100.00', 'update_zero_amount': '0.00'}
    assert saved.json()['amount'] == expected_amount.get(scenario, '250.00')
    assert saved.json()['client_id'] == client_id
    if is_update:
        assert saved_id == original_id
        assert saved.json()['deadline'] == '2030-06-01'
        assert saved.json()['notes'] == 'Keep existing notes'
    else:
        assert saved.json()['notes'] == note
