from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest
from redis.exceptions import ConnectionError as RedisConnectionError

from backend.app.models.constants import InvoiceStatus
from backend.app.models.database_models import Invoice
from backend.app.services import invoice as invoice_service


# Черновик прежней постановки. В 3.3 адаптировать к фактическому обработчику/воркеру,
# не требовать отдельную pay_invoice_with_cache и не переносить Redis в операцию БД.
pytestmark = pytest.mark.skip(reason='Отложено до 3.3: вызывающий слой оплаты ещё не реализован')


@pytest.mark.parametrize('scenario', ['success', 'repeat', 'rejected', 'missing', 'redis_failure'])
async def test_payment_invalidates_dashboard(
        scenario, bother_user, client, session_pool, redis_session, monkeypatch):
    headers, other_headers = bother_user
    me = await client.get('/auth/me', headers=headers)
    assert me.status_code == 200, me.text
    user_id = me.json()['id']
    other = await client.get('/auth/me', headers=other_headers)
    assert other.status_code == 200, other.text
    other_key = f"dashboard:{other.json()['id']}"
    response = await client.post('/clients', json={
        'client_name': 'Joe', 'organization': 'JoeCorp',
        'email': 'joecorp@example.com', 'client_status': 'lead',
    }, headers=headers)
    assert response.status_code == 201, response.text
    deal = await client.post('/deals', json={
        'name': 'Payment cache', 'amount': '100.00', 'client_id': response.json()['id'],
    }, headers=headers)
    assert deal.status_code == 201, deal.text
    response = await client.post('/invoices', json={
        'label': 'Pay me', 'amount': '40.00', 'deal_id': deal.json()['id'],
        'due_date': str(datetime.now(timezone.utc).date() + timedelta(days=1)),
    }, headers=headers)
    assert response.status_code == 201, response.text
    invoice_id = response.json()['id']
    initial_paid_at = datetime(2026, 1, 1, tzinfo=timezone.utc) if scenario == 'repeat' else None
    async with session_pool() as session:
        async with session.begin():
            invoice = await session.get(Invoice, invoice_id)
            invoice.status = InvoiceStatus.PAID if scenario == 'repeat' else InvoiceStatus.ISSUED
            invoice.issue_version = 1
            invoice.is_paid = scenario == 'repeat'
            invoice.paid_at = initial_paid_at

    key = f'dashboard:{user_id}'
    await redis_session.set(key, 'old summary')
    await redis_session.set(other_key, 'other summary')
    original_delete = redis_session.delete
    deleted_keys = []

    async def checked_delete(*keys):
        # Независимая сессия видит PAID: удаление кэша должно идти после commit.
        async with session_pool() as observer:
            saved = await observer.get(Invoice, invoice_id)
            assert saved.status == InvoiceStatus.PAID
            assert saved.paid_at is not None
        deleted_keys.extend(keys)
        if scenario == 'redis_failure':
            raise RedisConnectionError('Controlled cache failure')
        return await original_delete(*keys)

    monkeypatch.setattr(redis_session, 'delete', checked_delete)
    async with session_pool() as session:
        arguments = {
            'invoice_id': '00000000000000000000000000' if scenario == 'missing' else invoice_id,
            'user_id': user_id, 'expected_issue_version': 0 if scenario == 'rejected' else 1,
            'session': session, 'redis': redis_session,
        }
        if scenario == 'rejected':
            with pytest.raises(ValueError):
                await invoice_service.pay_invoice_with_cache(**arguments)
        elif scenario == 'redis_failure':
            with pytest.raises(RedisConnectionError):
                await invoice_service.pay_invoice_with_cache(**arguments)
        else:
            result = await invoice_service.pay_invoice_with_cache(**arguments)
            if scenario == 'missing':
                assert result is None
            else:
                assert result.status == InvoiceStatus.PAID
        assert not session.in_transaction()

    assert deleted_keys == ([] if scenario in ('rejected', 'missing') else [key])
    assert await redis_session.get(other_key) == 'other summary'
    assert await redis_session.get(key) == (
        None if scenario in ('success', 'repeat') else 'old summary'
    )
    async with session_pool() as session:
        saved = await session.get(Invoice, invoice_id)
        assert saved.amount == Decimal('40.00')
        assert saved.issue_version == 1
        if scenario in ('rejected', 'missing'):
            assert saved.status == InvoiceStatus.ISSUED
            assert saved.paid_at is None
        else:
            assert saved.status == InvoiceStatus.PAID
            assert saved.paid_at is not None
            if scenario == 'repeat':
                assert saved.paid_at == initial_paid_at
