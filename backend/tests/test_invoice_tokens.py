from datetime import datetime, timedelta, timezone
from urllib.parse import urlsplit

import pytest
from sqlalchemy import select

from backend.app.models.constants import InvoiceStatus
from backend.app.models.database_models import Invoice, Token
from backend.app.services import invoice as invoice_service
from fastapi.exceptions import ResponseValidationError


@pytest.mark.parametrize('scenario, expected_code', [
    ('success', 200), ('repeat', 200), ('expired', 409),
    ('wrong', 404), ('missing', 404), ('revoked', 404), ('stale', 404),
])
async def test_public_payment_post(
        scenario, expected_code, token_invoice, client, session_pool):
    invoice_id, user_id = token_invoice
    async with session_pool() as session:
        await invoice_service.issue_invoice_in_db(invoice_id, user_id, session)
    async with session_pool() as session:
        token = await session.scalar(select(Token).where(Token.invoice_id == invoice_id))
        secret = token.token_value
    if scenario in ('revoked', 'stale'):
        async with session_pool() as session:
            await invoice_service.revoke_invoice_in_db(invoice_id, user_id, session)
        if scenario == 'stale':
            async with session_pool() as session:
                await invoice_service.issue_invoice_in_db(invoice_id, user_id, session)
    if scenario == 'repeat':
        async with session_pool() as session:
            await invoice_service.pay_invoice_in_db(invoice_id, user_id, 1, session)
    if scenario == 'expired':
        async with session_pool() as session:
            async with session.begin():
                invoice = await session.get(Invoice, invoice_id)
                invoice.due_date = datetime.now(timezone.utc).date() - timedelta(days=1)
    async with session_pool() as session:
        invoice = await session.get(Invoice, invoice_id)
        before = (invoice.status, invoice.issue_version, invoice.paid_at)
    target_id = '00000000000000000000000000' if scenario == 'missing' else invoice_id
    supplied = 'incorrect-secret' if scenario == 'wrong' else secret
    response = await client.post(f'/invoices/{target_id}/{supplied}/pay')
    assert response.status_code == expected_code, response.text
    async with session_pool() as session:
        saved = await session.get(Invoice, invoice_id)
        if expected_code == 200:
            assert saved.status == InvoiceStatus.PAID
            assert saved.paid_at is not None
            assert saved.issue_version == before[1]
            if scenario == 'repeat':
                assert saved.paid_at == before[2]
            assert response.json()['status'] == 'paid'
            assert datetime.fromisoformat(response.json()['paid_at']) == saved.paid_at
            assert response.json()['can_pay'] is False
            assert response.json()['is_overdue'] is False
        else:
            assert (saved.status, saved.issue_version, saved.paid_at) == before
            if expected_code == 404:
                assert response.json() == {'detail': 'Invoice not found'}


@pytest.mark.parametrize('scenario', [
    'issued', 'paid', 'wrong', 'stale', 'link',
    'due_today', 'expired', 'paid_after_deadline', 'draft', 'cancelled',
])
async def test_public_invoice_read(
        scenario, token_invoice, active_user, client, session_pool, monkeypatch):
    invoice_id, user_id = token_invoice
    async with session_pool() as session:
        await invoice_service.issue_invoice_in_db(invoice_id, user_id, session)
    if scenario in ('paid', 'paid_after_deadline'):
        async with session_pool() as session:
            await invoice_service.pay_invoice_in_db(invoice_id, user_id, 1, session)
    async with session_pool() as session:
        async with session.begin():
            token = await session.scalar(select(Token).where(Token.invoice_id == invoice_id))
            secret = token.token_value
            if scenario == 'stale':
                token.issue_version = 0
            invoice = await session.get(Invoice, invoice_id)
            today = datetime.now(timezone.utc).date()
            if scenario == 'due_today':
                invoice.due_date = today
            if scenario in ('expired', 'paid_after_deadline'):
                invoice.due_date = today - timedelta(days=1)
            if scenario in ('draft', 'cancelled'):
                # Models a status changed after the token was already read.
                invoice.status = InvoiceStatus(scenario)
            before = (invoice.status, invoice.issue_version, invoice.paid_at)
    fixed_now = datetime.combine(today, datetime.min.time(), tzinfo=timezone.utc)
    monkeypatch.setattr('backend.app.api.routes.invoices.get_datetime_utc', lambda: fixed_now)
    # Exercise the registered handler as well as the actual owner-facing link.
    path = f'/invoices/{invoice_id}/{secret}'
    if scenario == 'wrong':
        path = f'/invoices/{invoice_id}/incorrect-secret'
    if scenario == 'link':
        response = await client.get(
            f'/invoices/{invoice_id}/payment-link', headers=active_user[0])
        assert response.status_code == 200
        path = urlsplit(response.json()['payment_url']).path
    try:
        response = await client.get(path)
    except ResponseValidationError:
        pytest.fail('Public invoice response does not match InvoiceSecretRead', pytrace=False)
    async with session_pool() as session:
        saved = await session.get(Invoice, invoice_id)
        assert (saved.status, saved.issue_version, saved.paid_at) == before
    if scenario in ('wrong', 'stale', 'draft', 'cancelled'):
        assert response.status_code == 404, response.text
        missing = await client.get('/invoices/00000000000000000000000000/incorrect-secret')
        assert missing.status_code == 404
        assert response.json() == missing.json()
    else:
        assert response.status_code == 200, response.text
        assert set(response.json()) == {
            'number', 'label', 'amount', 'currency', 'due_date',
            'status', 'paid_at', 'is_overdue', 'can_pay',
        }
        assert response.json()['can_pay'] == (scenario not in ('paid', 'expired', 'paid_after_deadline'))
        assert response.json()['is_overdue'] == (scenario == 'expired')


@pytest.mark.parametrize('scenario, expected_code', [
    ('issued', 200), ('paid', 200), ('draft', 409),
    ('revoke', 409), ('cancel', 409), ('missing', 404),
    ('foreign', 404), ('anonymous', 401),
])
async def test_payment_link_http(
        scenario, expected_code, token_invoice, active_user, other_active_user,
        client, session_pool):
    invoice_id, user_id = token_invoice
    headers = active_user[0]
    if scenario != 'draft':
        async with session_pool() as session:
            await invoice_service.issue_invoice_in_db(invoice_id, user_id, session)
    if scenario in ('revoke', 'cancel', 'paid'):
        async with session_pool() as session:
            if scenario == 'paid':
                await invoice_service.pay_invoice_in_db(invoice_id, user_id, 1, session)
            else:
                await getattr(invoice_service, f'{scenario}_invoice_in_db')(
                    invoice_id, user_id, session)
    target_id = invoice_id
    if scenario == 'missing':
        target_id = '00000000000000000000000000'
    if scenario == 'foreign':
        headers = other_active_user
    if scenario == 'anonymous':
        headers = {}
    async with session_pool() as session:
        invoice = await session.get(Invoice, invoice_id)
        before = (invoice.status, invoice.issue_version, invoice.paid_at)
        token = await session.scalar(select(Token).where(Token.invoice_id == invoice_id))
        token_value = token.token_value if token else None
    response = await client.get(f'/invoices/{target_id}/payment-link', headers=headers)
    assert response.status_code == expected_code, response.text
    repeated = await client.get(f'/invoices/{target_id}/payment-link', headers=headers)
    assert repeated.status_code == expected_code, repeated.text
    assert repeated.json() == response.json()
    async with session_pool() as session:
        invoice = await session.get(Invoice, invoice_id)
        assert (invoice.status, invoice.issue_version, invoice.paid_at) == before
        token = await session.scalar(select(Token).where(Token.invoice_id == invoice_id))
        assert (token.token_value if token else None) == token_value
    if expected_code == 200:
        assert set(response.json()) == {'payment_url'}
        payment_url = response.json()['payment_url']
        parsed = urlsplit(payment_url)
        assert parsed.scheme in ('http', 'https') and parsed.netloc, payment_url
        assert token_value in payment_url
    else:
        assert 'payment_url' not in response.json()
        if token_value:
            assert token_value not in response.text


@pytest.fixture
async def token_invoice(active_user, client):
    headers, _ = active_user
    me = await client.get('/auth/me', headers=headers)
    assert me.status_code == 200, me.text
    customer = await client.post('/clients', json={
        'client_name': 'Joe', 'organization': 'JoeCorp',
        'email': 'joe@example.com', 'client_status': 'lead',
    }, headers=headers)
    assert customer.status_code == 201, customer.text
    deal = await client.post('/deals', json={
        'name': 'Token lifecycle', 'amount': '100.00',
        'client_id': customer.json()['id'],
    }, headers=headers)
    assert deal.status_code == 201, deal.text
    response = await client.post('/invoices', json={
        'label': 'Token invoice', 'amount': '100.00',
        'deal_id': deal.json()['id'],
        'due_date': (datetime.now(timezone.utc).date() + timedelta(days=30)).isoformat(),
    }, headers=headers)
    assert response.status_code == 201, response.text
    return response.json()['id'], me.json()['id']


@pytest.mark.parametrize('action', ['revoke', 'cancel', 'pay'])
async def test_invoice_token_lifecycle(action, token_invoice, session_pool):
    invoice_id, user_id = token_invoice
    async with session_pool() as session:
        assert await session.scalar(select(Token).where(Token.invoice_id == invoice_id)) is None
    async with session_pool() as session:
        await invoice_service.issue_invoice_in_db(invoice_id, user_id, session)
    async with session_pool() as session:
        token = (await session.scalars(select(Token).where(Token.invoice_id == invoice_id))).one()
        old_value = token.token_value
        assert isinstance(old_value, str) and old_value
        assert token.issue_version == 1
    async with session_pool() as session:
        if action == 'pay':
            await invoice_service.pay_invoice_in_db(invoice_id, user_id, 1, session)
        else:
            operation = getattr(invoice_service, f'{action}_invoice_in_db')
            await operation(invoice_id, user_id, session)
    async with session_pool() as session:
        token = await session.scalar(select(Token).where(Token.invoice_id == invoice_id))
        if action == 'pay':
            assert token is not None
            assert token.token_value == old_value
            assert token.issue_version == 1
        else:
            assert token is None
    if action == 'revoke':
        async with session_pool() as session:
            await invoice_service.issue_invoice_in_db(invoice_id, user_id, session)
        async with session_pool() as session:
            token = (await session.scalars(select(Token).where(Token.invoice_id == invoice_id))).one()
            assert token.token_value != old_value
            assert token.issue_version == 2
            assert await session.scalar(select(Token).where(Token.token_value == old_value)) is None


async def test_rejected_issue_creates_no_token(token_invoice, session_pool):
    invoice_id, user_id = token_invoice
    async with session_pool() as session:
        async with session.begin():
            invoice = await session.get(Invoice, invoice_id)
            invoice.amount = 101
    async with session_pool() as session:
        with pytest.raises(ValueError):
            await invoice_service.issue_invoice_in_db(invoice_id, user_id, session)
    async with session_pool() as session:
        invoice = await session.get(Invoice, invoice_id)
        assert invoice.status == InvoiceStatus.DRAFT
        assert invoice.issue_version == 0
        assert await session.scalar(select(Token).where(Token.invoice_id == invoice_id)) is None


@pytest.mark.parametrize('action', ['issue', 'revoke', 'cancel'])
async def test_token_change_rolls_back_with_invoice(
        action, token_invoice, session_pool, monkeypatch):
    invoice_id, user_id = token_invoice
    old_value = None
    if action != 'issue':
        async with session_pool() as session:
            await invoice_service.issue_invoice_in_db(invoice_id, user_id, session)
        async with session_pool() as session:
            token = await session.scalar(select(Token).where(Token.invoice_id == invoice_id))
            old_value = token.token_value

    helper_name = 'create_token' if action == 'issue' else 'delete_token_by_invoice_id'
    original = getattr(invoice_service, helper_name)

    async def fail_after_flush(**kwargs):
        await original(**kwargs)
        await kwargs['session'].flush()
        raise RuntimeError('Simulated failure before commit')

    monkeypatch.setattr(invoice_service, helper_name, fail_after_flush)
    async with session_pool() as session:
        operation = getattr(invoice_service, f'{action}_invoice_in_db')
        with pytest.raises(RuntimeError, match='Simulated failure before commit'):
            await operation(invoice_id, user_id, session)
    async with session_pool() as session:
        invoice = await session.get(Invoice, invoice_id)
        token = await session.scalar(select(Token).where(Token.invoice_id == invoice_id))
        if action == 'issue':
            assert invoice.status == InvoiceStatus.DRAFT
            assert invoice.issue_version == 0
            assert token is None
        else:
            assert invoice.status == InvoiceStatus.ISSUED
            assert invoice.issue_version == 1
            assert token is not None
            assert token.token_value == old_value
            assert token.issue_version == 1
