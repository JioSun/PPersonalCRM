from datetime import datetime, timedelta, timezone

import pytest

from ..app.models.constants import InvoiceStatus
from ..app.models.database_models import Invoice


@pytest.mark.parametrize(
    'hour, minute, second', [(12, 0, 0), (23, 59, 30), (23, 59, 50)]
)
async def test_dashboard_refreshes_after_utc_midnight(
    hour, minute, second, active_user, client, session_pool, redis_session, monkeypatch
):
    now = datetime(2026, 10, 14, hour, minute, second, tzinfo=timezone.utc)

    def current_time():
        return now

    monkeypatch.setattr('backend.app.models.utils.get_datetime_utc', current_time)
    monkeypatch.setattr(
        'backend.app.api.routes.dashboards.get_datetime_utc',
        current_time,
        raising=False,
    )
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
            'name': 'Midnight work',
            'amount': '100.00',
            'client_id': response.json()['id'],
        },
        headers=headers,
    )
    assert deal.status_code == 201, deal.text
    response = await client.post(
        '/invoices',
        json={
            'label': 'Due today',
            'amount': '40.00',
            'deal_id': deal.json()['id'],
            'due_date': '2026-10-14',
        },
        headers=headers,
    )
    assert response.status_code == 201, response.text
    invoice_id = response.json()['id']
    async with session_pool() as session:
        async with session.begin():
            invoice = await session.get(Invoice, invoice_id)
            assert invoice is not None
            invoice.status = InvoiceStatus.ISSUED
            invoice.issue_version = 1

    original_set = redis_session.set
    expires_at = None

    async def set_with_test_clock(name, value, **kwargs):
        nonlocal expires_at
        assert kwargs.get('ex') is None, (
            'Use a single expiry option, not EX together with EXAT'
        )
        midnight = now.replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(
            days=1
        )
        expected = int(min(now + timedelta(seconds=60), midnight).timestamp())
        assert kwargs.get('exat') == expected
        expires_at = expected
        return await original_set(name, value, ex=expected - int(now.timestamp()))

    monkeypatch.setattr(redis_session, 'set', set_with_test_clock)
    response = await client.get('/dashboard', headers=headers)
    assert response.status_code == 200, response.text
    before = response.json()
    assert before['overdue_count'] == 0
    assert before['overdue_invoice'] == []
    assert await redis_session.get(f'dashboard:{user_id}') is not None

    # Имитируем истечение по уже проверенному EXAT, не ждём реальной полуночи.
    now = datetime(2026, 10, 15, 0, 0, 1, tzinfo=timezone.utc)
    assert expires_at <= int(now.timestamp())
    await redis_session.delete(f'dashboard:{user_id}')
    response = await client.get('/dashboard', headers=headers)
    assert response.status_code == 200, response.text
    after = response.json()
    assert after['overdue_count'] == 1
    assert after['overdue_amount'] == '40.00'
    assert {item['invoice_id'] for item in after['overdue_invoice']} == {invoice_id}
    assert after['unpaid_amount'] == before['unpaid_amount'] == '40.00'
    assert after['paid_amount'] == before['paid_amount']

    async with session_pool() as session:
        invoice = await session.get(Invoice, invoice_id)
        assert invoice is not None
        assert invoice.status == InvoiceStatus.ISSUED
        assert invoice.issue_version == 1
