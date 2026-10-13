import asyncio
from datetime import datetime, timezone
from decimal import Decimal

import pytest
from sqlalchemy import text

from backend.app.models.constants import InvoiceStatus
from backend.app.models.database_models import Deal, Invoice


async def test_deal_limit_rejection_ends_transaction(active_user, client, session_pool):
    from backend.app.crud.deal import update_deal_by_id
    from backend.app.schemas.deal import DealUpdate

    headers, login_response = active_user
    me = await client.get('/auth/me', headers=headers)
    assert me.status_code == 200, me.text
    user_id = me.json()['id']
    response = await client.post('/clients', json={
        'client_name': 'Joe', 'organization': 'JoeCorp',
        'email': 'joecorp@example.com', 'client_status': 'lead',
    }, headers=headers)
    assert response.status_code == 201, response.text
    deal = await client.post('/deals', json={
        'name': 'Original', 'amount': '100.00',
        'client_id': response.json()['id'],
    }, headers=headers)
    assert deal.status_code == 201, deal.text
    deal_id = deal.json()['id']
    response = await client.post('/invoices', json={
        'label': 'Occupied', 'amount': '70.00',
        'deal_id': deal_id, 'due_date': '2000-01-01',
    }, headers=headers)
    assert response.status_code == 201, response.text
    async with session_pool() as session:
        async with session.begin():
            invoice = await session.get(Invoice, response.json()['id'])
            assert invoice is not None
            invoice.status = InvoiceStatus.ISSUED
            invoice.issue_version = 1

    async with session_pool() as session:
        with pytest.raises(ValueError):
            await update_deal_by_id(
                deal_id=deal_id, user_id=user_id,
                deal_in=DealUpdate(amount=Decimal('60.00'), name='Changed'),
                session=session,
            )
        assert session.in_transaction() is False
        assert not session.dirty

    async with session_pool() as session:
        saved = await session.get(Deal, deal_id)
        assert saved is not None
        assert saved.amount == Decimal('100.00')
        assert saved.name == 'Original'


@pytest.mark.parametrize('body, expected_code, expected_amount', [
    ({'amount': '70.00', 'name': 'Changed'}, 200, '70.00'),
    ({'amount': '69.99', 'name': 'Changed'}, 409, '100.00'),
    ({'amount': '120.00', 'name': 'Changed'}, 200, '120.00'),
    ({'name': 'Changed'}, 200, '100.00'),
])
async def test_deal_limit_http(
        body, expected_code, expected_amount, active_user, client, session_pool, redis_session):
    headers, login_response = active_user
    me = await client.get('/auth/me', headers=headers)
    assert me.status_code == 200, me.text
    user_id = me.json()['id']
    response = await client.post('/clients', json={
        'client_name': 'Joe', 'organization': 'JoeCorp',
        'email': 'joecorp@example.com', 'client_status': 'lead',
    }, headers=headers)
    assert response.status_code == 201, response.text
    deal = await client.post('/deals', json={
        'name': 'Original', 'amount': '100.00',
        'client_id': response.json()['id'],
    }, headers=headers)
    assert deal.status_code == 201, deal.text
    deal_id = deal.json()['id']

    for status, amount in [
        (InvoiceStatus.ISSUED, '40.00'), (InvoiceStatus.PAID, '30.00'),
        (InvoiceStatus.DRAFT, '500.00'), (InvoiceStatus.CANCELLED, '500.00'),
    ]:
        response = await client.post('/invoices', json={
            'label': status.value, 'amount': amount,
            'deal_id': deal_id, 'due_date': '2000-01-01',
        }, headers=headers)
        assert response.status_code == 201, response.text
        async with session_pool() as session:
            async with session.begin():
                invoice = await session.get(Invoice, response.json()['id'])
                assert invoice is not None
                invoice.status = status
                if status == InvoiceStatus.PAID:
                    invoice.is_paid = True
                    invoice.paid_at = datetime(2000, 1, 1, tzinfo=timezone.utc)

    await redis_session.set(f'dashboard:{user_id}', 'cached summary')
    response = await client.patch(f'/deals/{deal_id}', json=body, headers=headers)
    assert response.status_code == expected_code, response.text
    async with session_pool() as session:
        saved = await session.get(Deal, deal_id)
        assert saved is not None
        assert saved.amount == Decimal(expected_amount)
        assert saved.name == ('Changed' if expected_code == 200 else 'Original')
    assert await redis_session.get(f'dashboard:{user_id}') == (
        None if expected_code == 200 else 'cached summary'
    )


async def test_deal_limit_after_concurrent_issue(
        active_user, client, session_pool, monkeypatch):
    from backend.app.services.invoice import get_invoice_for_transition, issue_invoice_in_db

    headers, login_response = active_user
    me = await client.get('/auth/me', headers=headers)
    assert me.status_code == 200, me.text
    user_id = me.json()['id']
    response = await client.post('/clients', json={
        'client_name': 'Joe', 'organization': 'JoeCorp',
        'email': 'joecorp@example.com', 'client_status': 'lead',
    }, headers=headers)
    assert response.status_code == 201, response.text
    deal = await client.post('/deals', json={
        'name': 'Original', 'amount': '100.00',
        'client_id': response.json()['id'],
    }, headers=headers)
    assert deal.status_code == 201, deal.text
    deal_id = deal.json()['id']
    response = await client.post('/invoices', json={
        'label': 'Concurrent', 'amount': '80.00',
        'deal_id': deal_id, 'due_date': '2000-01-01',
    }, headers=headers)
    assert response.status_code == 201, response.text
    invoice_id = response.json()['id']
    issue_locked = asyncio.Event()
    allow_issue = asyncio.Event()
    backend_pids = {}

    async def controlled_transition(invoice_id, user_id, session):
        invoice = await get_invoice_for_transition(
            invoice_id=invoice_id, user_id=user_id, session=session,
        )
        backend_pids['issue'] = await session.scalar(text('SELECT pg_backend_pid()'))
        issue_locked.set()
        await allow_issue.wait()
        return invoice

    monkeypatch.setattr(
        'backend.app.services.invoice.get_invoice_for_transition', controlled_transition,
    )
    async with session_pool() as issue_session:
        tasks = []
        try:
            issue_task = asyncio.create_task(issue_invoice_in_db(
                invoice_id=invoice_id, user_id=user_id, session=issue_session,
            ))
            tasks.append(issue_task)
            await asyncio.wait_for(issue_locked.wait(), timeout=10)
            patch_task = asyncio.create_task(client.patch(
                f'/deals/{deal_id}', json={'amount': '60.00', 'name': 'Changed'}, headers=headers,
            ))
            tasks.append(patch_task)

            async def wait_for_blocked_patch():
                async with session_pool() as observer:
                    while True:
                        assert not patch_task.done(), 'PATCH did not wait for the deal lock'
                        blocked = await observer.scalar(text(
                            'SELECT EXISTS (SELECT 1 FROM pg_stat_activity '
                            'WHERE :pid = ANY(pg_blocking_pids(pid)))'
                        ), {'pid': backend_pids['issue']})
                        # Новый снимок статистики: соединение PATCH могло появиться позже.
                        await observer.rollback()
                        if blocked:
                            return
                        await asyncio.sleep(0.01)

            # Подтверждаем ожидание SQL-блокировки до завершения выставления.
            await asyncio.wait_for(wait_for_blocked_patch(), timeout=10)
            allow_issue.set()
            issued, patched = await asyncio.wait_for(
                asyncio.gather(issue_task, patch_task), timeout=10,
            )
            assert issued.status == InvoiceStatus.ISSUED
            assert patched.status_code == 409, patched.text
        finally:
            allow_issue.set()
            for task in tasks:
                if not task.done():
                    task.cancel()
            await asyncio.gather(*tasks, return_exceptions=True)

    async with session_pool() as session:
        saved = await session.get(Deal, deal_id)
        invoice = await session.get(Invoice, invoice_id)
        assert saved is not None
        assert invoice is not None
        assert saved.amount == Decimal('100.00')
        assert saved.name == 'Original'
        assert invoice.status == InvoiceStatus.ISSUED
