from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest
from redis.exceptions import ConnectionError as RedisConnectionError
from sqlalchemy import select

from ..app.core.redis_py import get_redis
from ..app.models.constants import InvoiceStatus
from ..app.models.database_models import Invoice, Token


@pytest.mark.parametrize(
    'scenario',
    [
        'success',
        'repeat',
        'rejected',
        'missing',
        'wrong_token',
        'redis_failure',
        'repeat_redis_failure',
        'absent_cache',
        'service_rejected',
        'service_missing',
    ],
)
async def test_payment_invalidates_dashboard(
    scenario, bother_user, client, session_pool, redis_session, monkeypatch, caplog
):
    headers, other_headers = bother_user
    me = await client.get('/auth/me', headers=headers)
    assert me.status_code == 200, me.text
    user_id = me.json()['id']
    other = await client.get('/auth/me', headers=other_headers)
    assert other.status_code == 200, other.text
    other_key = f'dashboard:{other.json()["id"]}'
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
            'name': 'Payment cache',
            'amount': '100.00',
            'client_id': response.json()['id'],
        },
        headers=headers,
    )
    assert deal.status_code == 201, deal.text
    response = await client.post(
        '/invoices',
        json={
            'label': 'Pay me',
            'amount': '40.00',
            'deal_id': deal.json()['id'],
            'due_date': str(datetime.now(timezone.utc).date() + timedelta(days=1)),
        },
        headers=headers,
    )
    assert response.status_code == 201, response.text
    invoice_id = response.json()['id']
    issued = await client.post(f'/invoices/{invoice_id}/issue', headers=headers)
    assert issued.status_code == 200, issued.text
    is_repeat = scenario in ('repeat', 'repeat_redis_failure')
    redis_failure = scenario in ('redis_failure', 'repeat_redis_failure')
    refused = scenario in (
        'rejected',
        'missing',
        'wrong_token',
        'service_rejected',
        'service_missing',
    )
    initial_paid_at = datetime(2026, 1, 1, tzinfo=timezone.utc) if is_repeat else None
    async with session_pool() as session:
        async with session.begin():
            invoice = await session.get(Invoice, invoice_id)
            invoice.status = InvoiceStatus.PAID if is_repeat else InvoiceStatus.ISSUED
            invoice.is_paid = is_repeat
            invoice.paid_at = initial_paid_at
            if is_repeat or scenario == 'rejected':
                invoice.due_date = datetime.now(timezone.utc).date() - timedelta(days=1)
            token = await session.scalar(
                select(Token).where(Token.invoice_id == invoice_id)
            )
            secret = token.token_value

    key = f'dashboard:{user_id}'
    if scenario != 'absent_cache':
        await redis_session.set(key, 'old summary', ex=60)
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
        if redis_failure:
            raise RedisConnectionError('Controlled cache failure')
        return await original_delete(*keys)

    monkeypatch.setattr(redis_session, 'delete', checked_delete)
    if scenario in ('service_rejected', 'service_missing'):

        async def unavailable_payment(**kwargs):
            if scenario == 'service_rejected':
                raise ValueError('Payment rejected after initial link checks')
            return None

        monkeypatch.setattr(
            'backend.app.api.routes.invoices.pay_invoice_in_db', unavailable_payment
        )
    # Подмена только Redis-зависимости маршрута; middleware продолжает работать
    # со своим тестовым клиентом Redis. Бизнес-интерфейс остаётся HTTP.
    from ..app.main import app

    async def payment_redis():
        yield redis_session

    previous_override = app.dependency_overrides[get_redis]
    app.dependency_overrides[get_redis] = payment_redis
    target_id = '00000000000000000000000000' if scenario == 'missing' else invoice_id
    supplied = 'incorrect-secret' if scenario == 'wrong_token' else secret
    caplog.clear()
    try:
        response = await client.post(f'/invoices/{target_id}/{supplied}/pay')
    finally:
        app.dependency_overrides[get_redis] = previous_override
    expected_code = (
        409 if scenario in ('rejected', 'service_rejected') else 404 if refused else 200
    )
    assert response.status_code == expected_code, response.text
    if not refused:
        assert response.json()['status'] == 'paid'
        assert response.json()['can_pay'] is False
    if redis_failure:
        assert any(record.levelno >= 30 for record in caplog.records), (
            'Cache failure must be logged'
        )

    assert deleted_keys == ([] if refused else [key])
    assert await redis_session.get(other_key) == 'other summary'
    assert await redis_session.get(key) == (
        'old summary' if refused or redis_failure else None
    )
    async with session_pool() as session:
        saved = await session.get(Invoice, invoice_id)
        assert saved.amount == Decimal('40.00')
        assert saved.issue_version == 1
        if refused:
            assert saved.status == InvoiceStatus.ISSUED
            assert saved.paid_at is None
        else:
            assert saved.status == InvoiceStatus.PAID
            assert saved.paid_at is not None
            if is_repeat:
                assert saved.paid_at == initial_paid_at
