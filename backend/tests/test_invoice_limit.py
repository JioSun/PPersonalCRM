import asyncio
from datetime import datetime, timezone
from decimal import Decimal

import pytest

from ..app.models.constants import InvoiceStatus
from ..app.models.database_models import Deal, Invoice
from ..app.services.invoice import issue_invoice_in_db


@pytest.mark.parametrize(
    'amount, expected_code',
    [
        ('29.99', 200),
        ('30.00', 200),
        ('30.01', 409),
    ],
)
async def test_issue_invoice_limit_http(
    amount, expected_code, active_user, client, session_pool, redis_session
):
    headers, login_response = active_user
    me = await client.get('/auth/me', headers=headers)
    assert me.status_code == 200, me.text
    user_id = me.json()['id']

    response = await client.post(
        '/clients',
        json={
            'client_name': 'Joe',
            'organization': 'JoeCorp',
            'email': 'joecorp@example.com',
            'client_status': 'lead',
        },
        headers=headers,
    )
    assert response.status_code == 201, response.text
    deal = await client.post(
        '/deals',
        json={
            'name': 'Limit work',
            'amount': '100.00',
            'client_id': response.json()['id'],
        },
        headers=headers,
    )
    assert deal.status_code == 201, deal.text
    deal_id = deal.json()['id']

    invoice_ids = []
    for label, invoice_amount in [
        ('issued', '40.00'),
        ('paid', '30.00'),
        ('draft', '500.00'),
        ('cancelled', '500.00'),
        ('target', amount),
    ]:
        response = await client.post(
            '/invoices',
            json={
                'label': label,
                'amount': invoice_amount,
                'deal_id': deal_id,
                'due_date': '2000-01-01',
            },
            headers=headers,
        )
        assert response.status_code == 201, response.text
        invoice_ids.append(response.json()['id'])

    async with session_pool() as session:
        async with session.begin():
            for invoice_id, status in zip(
                invoice_ids,
                [
                    InvoiceStatus.ISSUED,
                    InvoiceStatus.PAID,
                    InvoiceStatus.DRAFT,
                    InvoiceStatus.CANCELLED,
                    InvoiceStatus.DRAFT,
                ],
            ):
                invoice = await session.get(Invoice, invoice_id)
                assert invoice is not None
                invoice.status = status
                invoice.issue_version = 3
                if status == InvoiceStatus.PAID:
                    invoice.is_paid = True
                    invoice.paid_at = datetime(2000, 1, 1, tzinfo=timezone.utc)

    await redis_session.set(f'dashboard:{user_id}', 'cached summary')
    response = await client.post(f'/invoices/{invoice_ids[-1]}/issue', headers=headers)
    assert response.status_code == expected_code, response.text

    async with session_pool() as session:
        invoice = await session.get(Invoice, invoice_ids[-1])
        saved_deal = await session.get(Deal, deal_id)
        assert invoice is not None
        assert saved_deal is not None
        assert saved_deal.amount == Decimal('100.00')
        assert invoice.amount == Decimal(amount)
        if expected_code == 200:
            assert invoice.status == InvoiceStatus.ISSUED
            assert invoice.issue_version == 4
            assert await redis_session.get(f'dashboard:{user_id}') is None
        else:
            assert invoice.status == InvoiceStatus.DRAFT
            assert invoice.issue_version == 3
            assert await redis_session.get(f'dashboard:{user_id}') == 'cached summary'


async def test_competitive_issue_limit(active_user, client, session_pool):
    headers, login_response = active_user
    me = await client.get('/auth/me', headers=headers)
    assert me.status_code == 200, me.text
    user_id = me.json()['id']
    response = await client.post(
        '/clients',
        json={
            'client_name': 'Joe',
            'organization': 'JoeCorp',
            'email': 'joecorp@example.com',
            'client_status': 'lead',
        },
        headers=headers,
    )
    assert response.status_code == 201, response.text
    deal = await client.post(
        '/deals',
        json={
            'name': 'Concurrent limit',
            'amount': '300.00',
            'client_id': response.json()['id'],
        },
        headers=headers,
    )
    assert deal.status_code == 201, deal.text
    invoice_ids = []
    for label in ['invoiceA', 'invoiceB']:
        response = await client.post(
            '/invoices',
            json={
                'label': label,
                'amount': '200.00',
                'deal_id': deal.json()['id'],
                'due_date': '2000-01-01',
            },
            headers=headers,
        )
        assert response.status_code == 201, response.text
        invoice_ids.append(response.json()['id'])

    async def issue_operation(invoice_id):
        async with session_pool() as session:
            return await issue_invoice_in_db(
                invoice_id=invoice_id,
                user_id=user_id,
                session=session,
            )

    results = await asyncio.wait_for(
        asyncio.gather(
            issue_operation(invoice_ids[0]),
            issue_operation(invoice_ids[1]),
            return_exceptions=True,
        ),
        timeout=10,
    )
    assert len([result for result in results if isinstance(result, Invoice)]) == 1, (
        results
    )
    assert len([result for result in results if isinstance(result, ValueError)]) == 1, (
        results
    )

    async with session_pool() as session:
        first = await session.get(Invoice, invoice_ids[0])
        second = await session.get(Invoice, invoice_ids[1])
        saved_deal = await session.get(Deal, deal.json()['id'])
        assert first is not None
        assert second is not None
        assert saved_deal is not None
        assert saved_deal.amount == Decimal('300.00')
        assert sorted([first.issue_version, second.issue_version]) == [0, 1]
        assert {first.status, second.status} == {
            InvoiceStatus.DRAFT,
            InvoiceStatus.ISSUED,
        }
        for invoice in [first, second]:
            assert invoice.issue_version == (
                1 if invoice.status == InvoiceStatus.ISSUED else 0
            )
