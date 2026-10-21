import asyncio
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal

import pytest
from sqlalchemy import text

from ..app.models.constants import InvoiceStatus
from ..app.models.database_models import Invoice
from ..app.services.invoice import (
    get_invoice_for_transition,
    issue_invoice_in_db,
    pay_invoice,
    pay_invoice_in_db,
    revoke_invoice_in_db,
)


@pytest.mark.parametrize('due_date', [date(2026, 10, 11), date(2026, 10, 12)])
def test_pay_invoice_success(due_date):
    now = datetime(2026, 10, 11, 23, 59, 59, tzinfo=timezone.utc)
    invoice = Invoice(
        label='invoiceA', amount=Decimal('100'), due_date=due_date,
        status=InvoiceStatus.ISSUED, issue_version=5, is_paid=False, paid_at=None,
    )

    pay_invoice(invoice, expected_issue_version=5, now=now)

    assert invoice.status == InvoiceStatus.PAID
    assert invoice.is_paid is True
    assert invoice.paid_at == now
    assert invoice.issue_version == 5


@pytest.mark.parametrize('initial_status, expected_version, due_date', [
    (InvoiceStatus.DRAFT, 5, date(2026, 10, 11)),
    (InvoiceStatus.CANCELLED, 5, date(2026, 10, 11)),
    (InvoiceStatus.ISSUED, 4, date(2026, 10, 11)),
    (InvoiceStatus.ISSUED, 6, date(2026, 10, 11)),
    (InvoiceStatus.PAID, 4, date(2026, 10, 11)),
    (InvoiceStatus.ISSUED, 5, date(2026, 10, 10)),
])
def test_pay_invoice_rejected_without_changes(initial_status, expected_version, due_date):
    now = datetime(2026, 10, 11, 0, 0, tzinfo=timezone.utc)
    initial_paid_at = None
    initial_is_paid = initial_status == InvoiceStatus.PAID
    if initial_is_paid:
        initial_paid_at = datetime(2026, 10, 10, 12, 0, tzinfo=timezone.utc)
    invoice = Invoice(
        label='invoiceA', amount=Decimal('100'), due_date=due_date,
        status=initial_status, issue_version=5,
        is_paid=initial_is_paid, paid_at=initial_paid_at,
    )

    with pytest.raises(ValueError):
        pay_invoice(invoice, expected_issue_version=expected_version, now=now)

    assert invoice.status == initial_status
    assert invoice.is_paid == initial_is_paid
    assert invoice.paid_at == initial_paid_at
    assert invoice.issue_version == 5


def test_pay_invoice_repeat_after_deadline():
    invoice = Invoice(
        label='invoiceA', amount=Decimal('100'), due_date=date(2026, 10, 11),
        status=InvoiceStatus.ISSUED, issue_version=5, is_paid=False, paid_at=None,
    )
    first_payment = datetime(2026, 10, 11, 12, 0, tzinfo=timezone.utc)
    pay_invoice(invoice, expected_issue_version=5, now=first_payment)

    pay_invoice(
        invoice, expected_issue_version=5,
        now=datetime(2026, 10, 12, 12, 0, tzinfo=timezone.utc),
    )

    assert invoice.status == InvoiceStatus.PAID
    assert invoice.is_paid is True
    assert invoice.paid_at == first_payment
    assert invoice.issue_version == 5


@pytest.mark.parametrize('scenario', [
    'success', 'repeat', 'draft', 'cancelled', 'old_version',
    'paid_old_version', 'expired', 'foreign', 'missing', 'rollback',
])
async def test_pay_invoice_transaction(
        scenario, clean_tables, session_pool, bother_user, client, monkeypatch):
    headers, other_headers = bother_user
    me = await client.get('/auth/me', headers=headers)
    assert me.status_code == 200, me.text
    user_id = me.json()['id']

    response = await client.post('/clients', json={
        'client_name': 'Joe', 'organization': 'JoeCorp',
        'email': 'joecorp@example.com', 'client_status': 'lead',
    }, headers=headers)
    assert response.status_code == 201, response.text

    deal = await client.post('/deals', json={
        'name': 'Test work', 'amount': '1000.00',
        'client_id': response.json()['id'],
    }, headers=headers)
    assert deal.status_code == 201, deal.text

    response = await client.post('/invoices', json={
        'label': 'invoiceA', 'amount': '100',
        'deal_id': deal.json()['id'], 'due_date': '2026-10-11',
    }, headers=headers)
    assert response.status_code == 201, response.text
    invoice_id = response.json()['id']

    # Fixed server time makes deadline checks independent of the test run date.
    now = datetime(2026, 10, 11, 12, 0, tzinfo=timezone.utc)

    class FixedDatetime:
        @classmethod
        def now(cls, tz):
            assert tz == timezone.utc
            return now

    monkeypatch.setattr('backend.app.services.invoice.datetime', FixedDatetime)

    initial_status = InvoiceStatus.ISSUED
    initial_paid_at = None
    due_date = date(2026, 10, 11)
    expected_version = 5
    if scenario == 'draft':
        initial_status = InvoiceStatus.DRAFT
    if scenario == 'cancelled':
        initial_status = InvoiceStatus.CANCELLED
    if scenario in ('repeat', 'paid_old_version'):
        initial_status = InvoiceStatus.PAID
        initial_paid_at = datetime(2026, 10, 10, 12, 0, tzinfo=timezone.utc)
        due_date = date(2026, 10, 10)
    if scenario == 'expired':
        due_date = date(2026, 10, 10)
    if scenario in ('old_version', 'paid_old_version'):
        expected_version = 4

    async with session_pool() as session:
        async with session.begin():
            invoice = await session.get(Invoice, invoice_id)
            assert invoice is not None
            invoice.status = initial_status
            invoice.issue_version = 5
            invoice.due_date = due_date
            invoice.is_paid = initial_status == InvoiceStatus.PAID
            invoice.paid_at = initial_paid_at

    target_id = invoice_id
    if scenario == 'missing':
        target_id = '00000000000000000000000000'
    if scenario == 'foreign':
        other_me = await client.get('/auth/me', headers=other_headers)
        assert other_me.status_code == 200, other_me.text
        user_id = other_me.json()['id']

    async with session_pool() as session:
        if scenario == 'rollback':
            async def fail_after_flush(invoice_id, user_id, session):
                invoice = await get_invoice_for_transition(
                    invoice_id=invoice_id, user_id=user_id, session=session)
                assert invoice is not None
                pay_invoice(invoice, expected_issue_version=expected_version, now=now)
                await session.flush()
                raise RuntimeError('simulated payment failure')

            monkeypatch.setattr(
                'backend.app.services.invoice.get_invoice_for_transition', fail_after_flush)
            with pytest.raises(RuntimeError, match='simulated payment failure'):
                await pay_invoice_in_db(
                    invoice_id=target_id, user_id=user_id,
                    expected_issue_version=expected_version, session=session,
                )
        elif scenario in ('draft', 'cancelled', 'old_version', 'paid_old_version', 'expired'):
            with pytest.raises(ValueError):
                await pay_invoice_in_db(
                    invoice_id=target_id, user_id=user_id,
                    expected_issue_version=expected_version, session=session,
                )
        else:
            result = await pay_invoice_in_db(
                invoice_id=target_id, user_id=user_id,
                expected_issue_version=expected_version, session=session,
            )
            if scenario in ('foreign', 'missing'):
                assert result is None
            else:
                assert result is not None
                assert result.status == InvoiceStatus.PAID
        assert session.in_transaction() is False

    async with session_pool() as session:
        invoice = await session.get(Invoice, invoice_id)
        assert invoice is not None
        assert invoice.issue_version == 5
        if scenario == 'success':
            assert invoice.status == InvoiceStatus.PAID
            assert invoice.is_paid is True
            assert invoice.paid_at == now
        else:
            assert invoice.status == initial_status
            assert invoice.is_paid == (initial_status == InvoiceStatus.PAID)
            assert invoice.paid_at == initial_paid_at


async def test_payment_locks_before_revoke(session_pool, active_user, client, monkeypatch):
    headers, login_response = active_user
    me = await client.get('/auth/me', headers=headers)
    assert me.status_code == 200, me.text
    user_id = me.json()['id']
    due_date = datetime.now(timezone.utc).date() + timedelta(days=1)

    response = await client.post('/clients', json={
        'client_name': 'Joe', 'organization': 'JoeCorp',
        'email': 'joecorp@example.com', 'client_status': 'lead',
    }, headers=headers)
    assert response.status_code == 201, response.text

    deal = await client.post('/deals', json={
        'name': 'Test work', 'amount': '1000.00',
        'client_id': response.json()['id'],
    }, headers=headers)
    assert deal.status_code == 201, deal.text

    response = await client.post('/invoices', json={
        'label': 'invoiceA', 'amount': '100',
        'deal_id': deal.json()['id'], 'due_date': str(due_date),
    }, headers=headers)
    assert response.status_code == 201, response.text
    invoice_id = response.json()['id']

    async with session_pool() as session:
        invoice = await issue_invoice_in_db(
            invoice_id=invoice_id, user_id=user_id, session=session)
        assert invoice is not None
        assert invoice.status == InvoiceStatus.ISSUED
        assert invoice.issue_version == 1

    payment_locked = asyncio.Event()
    allow_payment = asyncio.Event()
    revoke_started = asyncio.Event()
    backend_pids = {}

    async with session_pool() as payment_session, session_pool() as revoke_session:
        async def controlled_get_invoice_for_transition(invoice_id, user_id, session):
            # Сервис уже вошёл в session.begin(): не начинаем транзакцию раньше него.
            backend_pid = await session.scalar(text('SELECT pg_backend_pid()'))
            if session is payment_session:
                backend_pids['payment'] = backend_pid
            if session is revoke_session:
                backend_pids['revoke'] = backend_pid
                revoke_started.set()

            invoice = await get_invoice_for_transition(
                invoice_id=invoice_id, user_id=user_id, session=session)

            if session is payment_session:
                assert invoice is not None
                # Оригинальная функция уже захватила блокировки сделки и счёта.
                payment_locked.set()
                await allow_payment.wait()
            return invoice

        monkeypatch.setattr(
            'backend.app.services.invoice.get_invoice_for_transition',
            controlled_get_invoice_for_transition,
        )

        tasks = []
        try:
            payment_task = asyncio.create_task(pay_invoice_in_db(
                invoice_id=invoice_id, user_id=user_id,
                expected_issue_version=1, session=payment_session,
            ))
            tasks.append(payment_task)
            await asyncio.wait_for(payment_locked.wait(), timeout=10)

            revoke_task = asyncio.create_task(revoke_invoice_in_db(
                invoice_id=invoice_id, user_id=user_id, session=revoke_session,
            ))
            tasks.append(revoke_task)
            await asyncio.wait_for(revoke_started.wait(), timeout=10)

            assert backend_pids['payment'] != backend_pids['revoke']

            async def wait_for_database_lock():
                # Третья сессия наблюдает: занятую сессию отзыва трогать нельзя.
                async with session_pool() as observer_session:
                    while True:
                        assert not revoke_task.done(), 'Отзыв завершился, не дождавшись оплаты'
                        blockers = await observer_session.scalar(
                            text('SELECT pg_blocking_pids(:pid)'),
                            {'pid': backend_pids['revoke']},
                        )
                        if backend_pids['payment'] in blockers:
                            return
                        # Пауза лишь ограничивает частоту опроса, а не выбирает победителя.
                        await asyncio.sleep(0.01)

            # Разрешаем оплате продолжиться только после подтверждения ожидания в БД.
            await asyncio.wait_for(wait_for_database_lock(), timeout=10)
            allow_payment.set()
            results = await asyncio.wait_for(
                asyncio.gather(payment_task, revoke_task, return_exceptions=True),
                timeout=10,
            )
            assert isinstance(results[0], Invoice)
            assert isinstance(results[1], ValueError)
            assert payment_session.in_transaction() is False
            assert revoke_session.in_transaction() is False
        finally:
            # Не оставляем задачи и их транзакции жить после завершения теста.
            allow_payment.set()
            for task in tasks:
                if not task.done():
                    task.cancel()
            await asyncio.gather(*tasks, return_exceptions=True)

    async with session_pool() as session:
        invoice = await session.get(Invoice, invoice_id)
        assert invoice is not None
        assert invoice.status == InvoiceStatus.PAID
        assert invoice.is_paid is True
        assert invoice.paid_at is not None
        assert invoice.issue_version == 1


async def test_competitive_pay(session_pool, bother_user, client):
    headers, other_headers = bother_user
    me = await client.get('/auth/me', headers=headers)
    assert me.status_code == 200, me.text
    user_id = me.json()['id']
    date_now = datetime.now(timezone.utc).date() + timedelta(days=1)
    assert isinstance(date_now, date)
    response = await client.post('/clients', json={
        'client_name': 'Joe', 'organization': 'JoeCorp',
        'email': 'joecorp@example.com', 'client_status': 'lead',
    }, headers=headers)
    assert response.status_code == 201, response.text

    deal = await client.post('/deals', json={
        'name': 'Test work', 'amount': '1000.00',
        'client_id': response.json()['id'],
    }, headers=headers)
    assert deal.status_code == 201, deal.text

    response = await client.post('/invoices', json={
        'label': 'invoiceA', 'amount': '100',
        'deal_id': deal.json()['id'], 'due_date': str(date_now),
    }, headers=headers)
    assert response.status_code == 201, response.text
    invoice_id = response.json()['id']

    async with session_pool() as session:
        current_invoice = await issue_invoice_in_db(invoice_id=invoice_id, user_id=user_id, session=session)
        assert session.in_transaction() is False

    assert current_invoice is not None
    assert current_invoice.issue_version == 1
    assert current_invoice.status == InvoiceStatus.ISSUED

    async def payment_operation():
        async with session_pool() as session:
            return await pay_invoice_in_db(
                invoice_id=invoice_id,
                user_id=user_id,
                expected_issue_version=1,
                session=session,
            )

    async def revoke_operation():
        async with session_pool() as session:
            return await revoke_invoice_in_db(
                invoice_id=invoice_id,
                user_id=user_id,
                session=session,
            )

    results = await asyncio.gather(payment_operation(), revoke_operation(), return_exceptions=True)

    assert len([result for result in results if isinstance(result, Invoice)]) == 1
    assert len([result for result in results if isinstance(result, ValueError)]) == 1

    if isinstance(results[0], Invoice):
        async with session_pool() as session:
            current_invoice = await session.get(Invoice, invoice_id)
            assert current_invoice is not None
            assert current_invoice.issue_version == 1
            assert current_invoice.status == InvoiceStatus.PAID
            assert current_invoice.paid_at is not None
            assert current_invoice.is_paid is True
    else:
        async with session_pool() as session:
            current_invoice = await session.get(Invoice, invoice_id)
            assert current_invoice is not None
            assert current_invoice.issue_version == 1
            assert current_invoice.status == InvoiceStatus.DRAFT
            assert current_invoice.paid_at is  None
            assert current_invoice.is_paid is False
