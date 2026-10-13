from datetime import date, datetime, timezone
from decimal import Decimal

import pytest

from backend.app.models.constants import InvoiceStatus
from backend.app.models.database_models import Deal, Invoice


@pytest.mark.parametrize('scenario, expected_available, expected_remaining', [
    ('empty', '100.00', '100.00'),
    ('mixed', '34.65', '74.85'),
    ('excluded', '100.00', '100.00'),
    ('paid', '0.00', '0.00'),
    ('other_deal', '100.00', '100.00'),
])
async def test_deal_balances_http(
        scenario, expected_available, expected_remaining, active_user, client, session_pool):
    headers, login_response = active_user
    me = await client.get('/auth/me', headers=headers)
    assert me.status_code == 200, me.text
    response = await client.post('/clients', json={
        'client_name': 'Joe', 'organization': 'JoeCorp',
        'email': 'joecorp@example.com', 'client_status': 'lead',
    }, headers=headers)
    assert response.status_code == 201, response.text
    client_id = response.json()['id']
    deal = await client.post('/deals', json={
        'name': 'Balances', 'amount': '100.00', 'client_id': client_id,
    }, headers=headers)
    assert deal.status_code == 201, deal.text
    assert 'available_to_issue' not in deal.json()
    assert 'remaining_to_pay' not in deal.json()
    deal_id = deal.json()['id']
    invoice_deal_id = deal_id
    if scenario == 'other_deal':
        other = await client.post('/deals', json={
            'name': 'Other deal', 'amount': '100.00', 'client_id': client_id,
        }, headers=headers)
        assert other.status_code == 201, other.text
        invoice_deal_id = other.json()['id']

    rows = []
    if scenario in ('mixed', 'other_deal'):
        rows = [(InvoiceStatus.ISSUED, '40.20'), (InvoiceStatus.PAID, '25.15')]
    elif scenario == 'paid':
        rows = [(InvoiceStatus.PAID, '100.00')]
    if scenario in ('mixed', 'excluded'):
        rows += [(InvoiceStatus.DRAFT, '500.00'), (InvoiceStatus.CANCELLED, '500.00')]

    async with session_pool() as session:
        async with session.begin():
            for index, (status, amount) in enumerate(rows):
                session.add(Invoice(
                    label=f'Balance {index}', number=f'BAL-{index}',
                    amount=Decimal(amount), status=status, due_date=date(2000, 1, 1),
                    is_paid=status == InvoiceStatus.PAID,
                    paid_at=(datetime(2000, 1, 1, tzinfo=timezone.utc)
                             if status == InvoiceStatus.PAID else None),
                    user_id=me.json()['id'], client_id=client_id, deal_id=invoice_deal_id,
                ))

    for _ in range(2):
        response = await client.get(f'/deals/{deal_id}', headers=headers)
        assert response.status_code == 200, response.text
        body = response.json()
        assert body['id'] == deal_id
        assert body['amount'] == '100.00'
        assert isinstance(body['available_to_issue'], str)
        assert isinstance(body['remaining_to_pay'], str)
        assert Decimal(body['available_to_issue']) == Decimal(expected_available)
        assert Decimal(body['remaining_to_pay']) == Decimal(expected_remaining)

    async with session_pool() as session:
        saved = await session.get(Deal, deal_id)
        assert saved is not None
        assert saved.amount == Decimal('100.00')
        assert saved.name == 'Balances'
        assert saved.updated_at == datetime.fromisoformat(deal.json()['updated_at'])

    patched = await client.patch(f'/deals/{deal_id}', json={'name': 'Renamed'}, headers=headers)
    assert patched.status_code == 200, patched.text
    listed = await client.get('/deals', headers=headers)
    assert listed.status_code == 200, listed.text
    for body in [patched.json()]:
        assert 'available_to_issue' not in body
        assert 'remaining_to_pay' not in body


@pytest.mark.parametrize('scenario', ['foreign', 'missing'])
async def test_deal_balances_not_found(scenario, bother_user, client):
    headers, other_headers = bother_user
    response = await client.post('/clients', json={
        'client_name': 'Joe', 'organization': 'JoeCorp',
        'email': 'joecorp@example.com', 'client_status': 'lead',
    }, headers=headers)
    assert response.status_code == 201, response.text
    deal = await client.post('/deals', json={
        'name': 'Private deal', 'amount': '100.00', 'client_id': response.json()['id'],
    }, headers=headers)
    assert deal.status_code == 201, deal.text
    deal_id = deal.json()['id'] if scenario == 'foreign' else '00000000000000000000000000'
    response = await client.get(f'/deals/{deal_id}', headers=other_headers)
    assert response.status_code == 404, response.text
    assert response.json()['detail'] == 'Deal not found'
