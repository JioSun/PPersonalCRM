from datetime import date, datetime, timezone
from decimal import Decimal

import pytest

from backend.app.models.constants import InvoiceStatus
from backend.app.models.database_models import Client, Deal, Invoice


@pytest.mark.parametrize('scenario', ['empty', 'mixed'])
async def test_deal_list_finance(scenario, bother_user, client, session_pool):
    headers, other_headers = bother_user
    expected = {}
    for owner_headers in [headers, other_headers]:
        me = await client.get('/auth/me', headers=owner_headers)
        assert me.status_code == 200, me.text
        if scenario == 'empty' and owner_headers == headers:
            continue
        async with session_pool() as session:
            async with session.begin():
                customer = Client(client_name='List client', user_id=me.json()['id'])
                session.add(customer)
                await session.flush()
                for index, total in enumerate(['100.00', '200.00', '300.00']):
                    deal = Deal(
                        name=f'Finance {index}', amount=Decimal(total),
                        user_id=me.json()['id'], client_id=customer.id,
                    )
                    session.add(deal)
                    await session.flush()
                    rows = []
                    paid = '0.00'
                    if index == 1:
                        rows = [
                            (InvoiceStatus.PAID, '20.10'), (InvoiceStatus.PAID, '5.05'),
                            (InvoiceStatus.ISSUED, '40.00'), (InvoiceStatus.DRAFT, '500.00'),
                            (InvoiceStatus.CANCELLED, '500.00'),
                        ]
                        paid = '25.15'
                    elif index == 2:
                        rows = [(InvoiceStatus.PAID, '300.00')]
                        paid = '300.00'
                    for number, (status, amount) in enumerate(rows):
                        session.add(Invoice(
                            label=f'List {index}-{number}', number=f'LIST-{index}-{number}',
                            user_id=me.json()['id'], client_id=customer.id, deal_id=deal.id,
                            amount=Decimal(amount), status=status, due_date=date(2000, 1, 1),
                            is_paid=status == InvoiceStatus.PAID,
                            paid_at=(datetime(2000, 1, 1, tzinfo=timezone.utc)
                                     if status == InvoiceStatus.PAID else None),
                        ))
                    if owner_headers == headers:
                        expected[deal.id] = (total, paid, deal.name)

    response = await client.get('/deals', headers=headers)
    assert response.status_code == 200, response.text
    body = response.json()
    assert isinstance(body, list)
    assert {item['id'] for item in body} == set(expected)
    for item in body:
        total, paid, name = expected[item['id']]
        assert item['name'] == name
        assert item['currency'] == 'USD'
        for field in ['amount', 'paid_amount', 'remaining_to_pay']:
            assert isinstance(item[field], str)
        assert Decimal(item['amount']) == Decimal(total)
        assert Decimal(item['paid_amount']) == Decimal(paid)
        assert Decimal(item['remaining_to_pay']) == Decimal(total) - Decimal(paid)

    first = await client.get('/deals', params={'limit': 1, 'offset': 0}, headers=headers)
    second = await client.get('/deals', params={'limit': 2, 'offset': 1}, headers=headers)
    assert first.status_code == 200, first.text
    assert second.status_code == 200, second.text
    assert first.json() == body[:1]
    assert second.json() == body[1:3]
    beyond = await client.get('/deals', params={'offset': 20}, headers=headers)
    assert beyond.status_code == 200, beyond.text
    assert beyond.json() == []
    searched = await client.get('/deals', params={'q': 'Finance 1'}, headers=headers)
    assert searched.status_code == 200, searched.text
    assert searched.json() == [item for item in body if item['name'] == 'Finance 1']

    async with session_pool() as session:
        for deal_id, (total, paid, name) in expected.items():
            saved = await session.get(Deal, deal_id)
            assert saved is not None
            assert saved.amount == Decimal(total)
            assert saved.name == name
