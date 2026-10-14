from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest

from backend.app.crud.dashboard import get_dashboard_data, get_overdue_invoices
from backend.app.models.constants import InvoiceStatus
from backend.app.models.database_models import Invoice


async def test_dashboard_working(client, active_user):
    active_user = active_user[0]
    response = await client.get('/dashboard', headers={'Authorization': active_user['Authorization']})

    assert response.status_code == 200
    data = response.json()
    assert data["clients_summary"] == []
    assert data["overdue_invoice"] == []


@pytest.mark.parametrize('scenario', ['empty', 'mixed'])
@pytest.mark.parametrize('layer', ['crud', 'http'])
async def test_dashboard_financial_totals(
        scenario, layer, bother_user, client, session_pool, redis_session, monkeypatch):
    headers, other_headers = bother_user
    # EXAT использует реальные часы Redis; сроки счетов задаём относительно этого момента.
    now = datetime.now(timezone.utc)
    monkeypatch.setattr('backend.app.api.routes.dashboards.get_datetime_utc', lambda: now)
    today = now.date()
    overdue_id = None
    for owner_headers in [headers, other_headers]:
        me = await client.get('/auth/me', headers=owner_headers)
        assert me.status_code == 200, me.text
        owner_id = me.json()['id']
        if owner_headers == headers:
            user_id = owner_id
        response = await client.post('/clients', json={
            'client_name': 'Joe', 'organization': 'JoeCorp',
            'email': 'joecorp@example.com', 'client_status': 'lead',
        }, headers=owner_headers)
        assert response.status_code == 201, response.text
        client_id = response.json()['id']
        deal = await client.post('/deals', json={
            'name': 'Dashboard work', 'amount': '1000.00', 'client_id': client_id,
        }, headers=owner_headers)
        assert deal.status_code == 201, deal.text
        if owner_headers == headers:
            own_client_id = client_id
        if scenario == 'empty' and owner_headers == headers:
            continue
        async with session_pool() as session:
            async with session.begin():
                for index, (status, amount, days) in enumerate([
                    (InvoiceStatus.PAID, '25.15', -1),
                    (InvoiceStatus.ISSUED, '10.10', -1),
                    (InvoiceStatus.ISSUED, '20.20', 0),
                    (InvoiceStatus.ISSUED, '30.30', 1),
                    (InvoiceStatus.DRAFT, '100.00', -1),
                    (InvoiceStatus.CANCELLED, '200.00', -1),
                ]):
                    invoice = Invoice(
                        label=f'Summary {index}', number=f'SUM-{index}',
                        user_id=owner_id, client_id=client_id, deal_id=deal.json()['id'],
                        amount=Decimal(amount), status=status,
                        due_date=today + timedelta(days=days),
                        is_paid=status == InvoiceStatus.PAID,
                        paid_at=now if status == InvoiceStatus.PAID else None,
                    )
                    session.add(invoice)
                    await session.flush()
                    if owner_headers == headers and index == 1:
                        overdue_id = invoice.id

    expected = ('0', '0', '0', 0) if scenario == 'empty' else ('25.15', '60.60', '10.10', 1)
    if layer == 'crud':
        async with session_pool() as session:
            row = await get_dashboard_data(user_id=user_id, current_datetime=now, session=session)
            for name, value in zip(['paid_amount', 'unpaid_amount', 'overdue_amount'], expected[:3]):
                assert isinstance(getattr(row, name), Decimal)
                assert getattr(row, name) == Decimal(value)
            assert type(row.overdue_count) is int
            assert row.overdue_count == expected[3]
            overdue = await get_overdue_invoices(user_id=user_id, current_datetime=now, session=session)
            assert {invoice.id for invoice in overdue} == ({overdue_id} if overdue_id else set())
    else:
        await redis_session.delete(f'dashboard:{user_id}')
        response = await client.get('/dashboard', headers=headers)
        assert response.status_code == 200, response.text
        body = response.json()
        for name, value in zip(['paid_amount', 'unpaid_amount', 'overdue_amount'], expected[:3]):
            assert isinstance(body[name], str)
            assert Decimal(body[name]) == Decimal(value)
        assert type(body['overdue_count']) is int
        assert body['overdue_count'] == expected[3]
        assert {item['invoice_id'] for item in body['overdue_invoice']} == (
            {overdue_id} if overdue_id else set()
        )
        assert len(body['clients_summary']) == 1
        assert body['clients_summary'][0]['client_id'] == own_client_id
        assert Decimal(body['clients_summary'][0]['total_amount']) == Decimal('1000.00')
        assert await redis_session.get(f'dashboard:{user_id}') is not None

        async def unexpected_query(*args, **kwargs):
            pytest.fail('A cached response must not recalculate dashboard data')

        monkeypatch.setattr('backend.app.api.routes.dashboards.get_dashboard_data', unexpected_query)
        monkeypatch.setattr('backend.app.api.routes.dashboards.get_clients_sum', unexpected_query)
        monkeypatch.setattr('backend.app.api.routes.dashboards.get_overdue_invoices', unexpected_query)
        cached = await client.get('/dashboard', headers=headers)
        assert cached.status_code == 200, cached.text
        assert cached.json() == body
