from datetime import datetime, timezone

import pytest

from .conftest import active_user, session_pool
from ..app.models.constants import InvoiceStatus
from ..app.models.database_models import Invoice
from ..app.schemas.invoice import InvoiceUpdate
from ..app.services.invoice import delete_invoice_in_db, patch_invoice_in_db
from ..app.services.invoice import (get_invoice_for_transition,
                                    cancel_invoice_in_db,
                                    issue_invoice_in_db,
                                    revoke_invoice_in_db,
                                    cancel_invoice
                                    )


@pytest.mark.parametrize('action, initial_status, initial_version, expected_status, expected_version', [
    ('cancel', InvoiceStatus.DRAFT, 0, InvoiceStatus.CANCELLED, 0),
    ('cancel', InvoiceStatus.ISSUED, 1, InvoiceStatus.CANCELLED, 1),
    ('issue', InvoiceStatus.DRAFT, 0, InvoiceStatus.ISSUED, 1),
    ('revoke', InvoiceStatus.ISSUED, 1, InvoiceStatus.DRAFT, 1),
])
async def test_invoice_transition_http(
        action, initial_status, initial_version, expected_status, expected_version,
        clean_tables, session_pool, active_user, client, redis_session):
    headers, login_response = active_user

    client_json = {
        "client_name": "Joe",
        "organization": "JoeCorp",
        "email": "joecorp@example.com",
        "client_status": "lead",
    }
    response = await client.post('/clients', json=client_json, headers=headers)
    assert response.status_code == 201, response.text

    deal = await client.post('/deals', json={
        'name': 'Test work', 'amount': '1000.00',
        'client_id': response.json()['id'],
    }, headers=headers)
    assert deal.status_code == 201, deal.text

    invoice_json = {
        "label": "invoiceA",
        "amount": "100",
        "deal_id": deal.json()["id"],
        "due_date": "2021-04-01",
    }
    invoice = await client.post('/invoices', json=invoice_json, headers=headers)
    assert invoice.status_code == 201, invoice.text
    invoice_id = invoice.json()['id']

    async with session_pool() as session:
        async with session.begin():
            saved_invoice = await session.get(Invoice, invoice_id)
            assert saved_invoice is not None
            saved_invoice.status = initial_status
            saved_invoice.issue_version = initial_version

    me = await client.get('/auth/me', headers=headers)
    assert me.status_code == 200, me.text
    user_id = me.json()['id']
    await redis_session.set(f'dashboard:{user_id}', 'cached summary')

    response = await client.post(f'/invoices/{invoice_id}/{action}', headers=headers)
    assert response.status_code == 200, response.text
    assert response.json()['id'] == invoice_id
    assert response.json()['status'] == expected_status.value
    assert await redis_session.get(f'dashboard:{user_id}') is None

    async with session_pool() as session:
        saved_invoice = await session.get(Invoice, invoice_id)
        assert saved_invoice is not None
        assert saved_invoice.status == expected_status
        assert saved_invoice.issue_version == expected_version



@pytest.mark.parametrize('action, initial_status', [
    ('cancel', InvoiceStatus.PAID),
    ('cancel', InvoiceStatus.CANCELLED),
    ('issue', InvoiceStatus.ISSUED),
    ('issue', InvoiceStatus.PAID),
    ('issue', InvoiceStatus.CANCELLED),
    ('revoke', InvoiceStatus.DRAFT),
    ('revoke', InvoiceStatus.PAID),
    ('revoke', InvoiceStatus.CANCELLED),
])
async def test_invoice_transition_http_rejects_status(
        action, initial_status, clean_tables, session_pool, active_user, client, redis_session):
    headers, login_response = active_user

    client_json = {
        "client_name": "Joe",
        "organization": "JoeCorp",
        "email": "joecorp@example.com",
        "client_status": "lead",
    }
    response = await client.post('/clients', json=client_json, headers=headers)
    assert response.status_code == 201, response.text

    deal = await client.post('/deals', json={
        'name': 'Test work', 'amount': '1000.00',
        'client_id': response.json()['id'],
    }, headers=headers)
    assert deal.status_code == 201, deal.text

    invoice_json = {
        "label": "invoiceA",
        "amount": "100",
        "deal_id": deal.json()["id"],
        "due_date": "2021-04-01",
    }
    invoice = await client.post('/invoices', json=invoice_json, headers=headers)
    assert invoice.status_code == 201, invoice.text
    invoice_id = invoice.json()['id']

    initial_version = 3
    async with session_pool() as session:
        async with session.begin():
            saved_invoice = await session.get(Invoice, invoice_id)
            assert saved_invoice is not None
            saved_invoice.status = initial_status
            saved_invoice.issue_version = initial_version
            if initial_status == InvoiceStatus.PAID:
                saved_invoice.is_paid = True
                saved_invoice.paid_at = datetime.now(timezone.utc)

    me = await client.get('/auth/me', headers=headers)
    assert me.status_code == 200, me.text
    user_id = me.json()['id']
    await redis_session.set(f'dashboard:{user_id}', 'cached summary')

    response = await client.post(f'/invoices/{invoice_id}/{action}', headers=headers)
    assert response.status_code == 409, response.text
    assert await redis_session.get(f'dashboard:{user_id}') == 'cached summary'

    async with session_pool() as session:
        saved_invoice = await session.get(Invoice, invoice_id)
        assert saved_invoice is not None
        assert saved_invoice.status == initial_status
        assert saved_invoice.issue_version == initial_version


@pytest.mark.parametrize('action', ['cancel', 'issue', 'revoke'])
async def test_invoice_transition_http_other_user(
        action, clean_tables, session_pool, bother_user, client):
    headers, other_headers = bother_user

    client_json = {
        "client_name": "Joe",
        "organization": "JoeCorp",
        "email": "joecorp@example.com",
        "client_status": "lead",
    }
    response = await client.post('/clients', json=client_json, headers=headers)
    assert response.status_code == 201, response.text

    deal = await client.post('/deals', json={
        'name': 'Test work', 'amount': '1000.00',
        'client_id': response.json()['id'],
    }, headers=headers)
    assert deal.status_code == 201, deal.text

    invoice_json = {
        "label": "invoiceA",
        "amount": "100",
        "deal_id": deal.json()["id"],
        "due_date": "2021-04-01",
    }
    invoice = await client.post('/invoices', json=invoice_json, headers=headers)
    assert invoice.status_code == 201, invoice.text
    invoice_id = invoice.json()['id']

    response = await client.post(f'/invoices/{invoice_id}/{action}', headers=other_headers)
    assert response.status_code == 404, response.text
    assert response.json()['detail'] == 'Invoice not found'

    async with session_pool() as session:
        saved_invoice = await session.get(Invoice, invoice_id)
        assert saved_invoice is not None
        assert saved_invoice.status == InvoiceStatus.DRAFT
        assert saved_invoice.issue_version == 0


@pytest.mark.parametrize('action', ['cancel', 'issue', 'revoke'])
async def test_invoice_transition_http_missing(action, clean_tables, active_user, client):
    headers, login_response = active_user
    invoice_id = '00000000000000000000000000'

    response = await client.post(f'/invoices/{invoice_id}/{action}', headers=headers)
    assert response.status_code == 404, response.text
    assert response.json()['detail'] == 'Invoice not found'


@pytest.mark.parametrize('action', ['cancel', 'issue', 'revoke'])
async def test_invoice_transition_http_without_auth(action, clean_tables, client):
    invoice_id = '00000000000000000000000000'

    response = await client.post(f'/invoices/{invoice_id}/{action}')
    assert response.status_code == 401, response.text



@pytest.mark.parametrize('action', ['patch', 'delete'])
@pytest.mark.parametrize('initial_status', [
    InvoiceStatus.DRAFT, InvoiceStatus.ISSUED, InvoiceStatus.PAID, InvoiceStatus.CANCELLED,
])
async def test_patch_and_delete_invoice_in_db(
        action, initial_status, clean_tables, session_pool, active_user, client):
    headers, login_response = active_user
    me = await client.get('/auth/me', headers=headers)
    assert me.status_code == 200, me.text
    user_id = me.json()['id']

    response = await client.post('/clients', json={
        'client_name': 'Joe',
        'organization': 'JoeCorp',
        'email': 'joecorp@example.com',
        'client_status': 'lead',
    }, headers=headers)
    assert response.status_code == 201, response.text
    client_id = response.json()['id']

    deal = await client.post('/deals', json={
        'name': 'Test work', 'amount': '1000.00',
        'client_id': client_id,
    }, headers=headers)
    assert deal.status_code == 201, deal.text
    deal_id = deal.json()['id']

    response = await client.post('/invoices', json={
        'label': 'invoiceA', 'amount': '100',
        'deal_id': deal_id, 'due_date': '2021-04-01',
    }, headers=headers)
    assert response.status_code == 201, response.text
    invoice_id = response.json()['id']

    async with session_pool() as session:
        async with session.begin():
            invoice = await session.get(Invoice, invoice_id)
            assert invoice is not None
            invoice.status = initial_status
            invoice.issue_version = 3
            if initial_status == InvoiceStatus.PAID:
                invoice.is_paid = True
                invoice.paid_at = datetime.now(timezone.utc)

    async with session_pool() as session:
        if initial_status == InvoiceStatus.DRAFT:
            if action == 'patch':
                result = await patch_invoice_in_db(
                    invoice_id=invoice_id, user_id=user_id,
                    update_body=InvoiceUpdate(label='updated invoice'), session=session)
                assert result is not None
                assert result.label == 'updated invoice'
                assert result.updated_at is not None
            else:
                result = await delete_invoice_in_db(
                    invoice_id=invoice_id, user_id=user_id, session=session)
                assert result is True
        else:
            with pytest.raises(ValueError):
                if action == 'patch':
                    await patch_invoice_in_db(
                        invoice_id=invoice_id, user_id=user_id,
                        update_body=InvoiceUpdate(label='updated invoice'), session=session)
                else:
                    await delete_invoice_in_db(
                        invoice_id=invoice_id, user_id=user_id, session=session)
        assert session.in_transaction() is False

    async with session_pool() as session:
        invoice = await session.get(Invoice, invoice_id)
        if action == 'delete' and initial_status == InvoiceStatus.DRAFT:
            assert invoice is None
        else:
            assert invoice is not None
            assert invoice.status == initial_status
            assert invoice.issue_version == 3
            assert invoice.amount == 100
            assert invoice.due_date.isoformat() == '2021-04-01'
            assert invoice.deal_id == deal_id
            assert invoice.client_id == client_id
            if action == 'patch' and initial_status == InvoiceStatus.DRAFT:
                assert invoice.label == 'updated invoice'
            else:
                assert invoice.label == 'invoiceA'


async def test_invoice_transaction(clean_tables, session_pool, active_user, client):
    client_json = {
        "client_name": "Joe",
        "organization": "JoeCorp",
        "email": "joecorp@example.com",
        "client_status": "lead",
    }

    headers, login_response = active_user

    response = await client.post('/clients', json=client_json,
                                 headers={'Authorization': headers['Authorization']})

    assert response.status_code == 201

    deal = await client.post('/deals', json={
        'name': 'Test work', 'amount': '1000.00',
        'client_id': response.json()['id'],
    }, headers={'Authorization': headers['Authorization']})
    assert deal.status_code == 201, deal.text

    invoice_json = {
        "label": "invoiceA",
        "amount": "100",
        "deal_id": deal.json()["id"],
        "due_date": "2021-04-01",
    }

    invoice = await client.post('/invoices', json=invoice_json,
                                headers={'Authorization': headers['Authorization']})

    assert invoice.status_code == 201

    me = await client.get('/auth/me', headers={'Authorization': headers['Authorization']})
    assert me.status_code == 200, me.text
    user_id = me.json()['id']
    invoice_id = invoice.json()['id']
    async with session_pool() as session:
        cancel_invoice = await cancel_invoice_in_db(
            invoice_id=invoice_id,
            user_id=user_id,
            session=session,
        )

        assert cancel_invoice is not None
        assert cancel_invoice.status == InvoiceStatus.CANCELLED


    async with session_pool() as session:
        saved_invoice = await session.get(Invoice, invoice_id)

        assert saved_invoice is not None
        assert saved_invoice.status == InvoiceStatus.CANCELLED
        assert saved_invoice.issue_version == 0

@pytest.mark.parametrize('change_invoice_in_db',
                         [(cancel_invoice_in_db, InvoiceStatus.CANCELLED, 0),
                          (revoke_invoice_in_db, InvoiceStatus.DRAFT, 1),
                          (issue_invoice_in_db, InvoiceStatus.ISSUED, 1)])
async def test_invoice_repeating_cancelled(change_invoice_in_db, clean_tables, session_pool, active_user, client):
    client_json = {
        "client_name": "Joe",
        "organization": "JoeCorp",
        "email": "joecorp@example.com",
        "client_status": "lead",
    }

    headers, login_response = active_user
    change_invoice, status, version = change_invoice_in_db
    response = await client.post('/clients', json=client_json,
                                 headers={'Authorization': headers['Authorization']})

    assert response.status_code == 201

    deal = await client.post('/deals', json={
        'name': 'Test work', 'amount': '1000.00',
        'client_id': response.json()['id'],
    }, headers={'Authorization': headers['Authorization']})
    assert deal.status_code == 201, deal.text

    invoice_json = {
        "label": "invoiceA",
        "amount": "100",
        "deal_id": deal.json()["id"],
        "due_date": "2021-04-01",
    }

    invoice = await client.post('/invoices', json=invoice_json,
                                headers={'Authorization': headers['Authorization']})

    assert invoice.status_code == 201

    me = await client.get('/auth/me', headers={'Authorization': headers['Authorization']})
    assert me.status_code == 200, me.text
    user_id = me.json()['id']
    invoice_id = invoice.json()['id']
    if change_invoice == revoke_invoice_in_db:
        async with session_pool() as session:
            get_issued_invoice = await issue_invoice_in_db(invoice_id=invoice_id, user_id=user_id, session=session)
            assert get_issued_invoice is not None
            assert get_issued_invoice.status == InvoiceStatus.ISSUED
    async with session_pool() as session:
        get_changed_invoice = await change_invoice(invoice_id=invoice_id, session=session, user_id=user_id)
        assert get_changed_invoice is not None
        assert get_changed_invoice.status == status

    async with session_pool() as session:
        with pytest.raises(ValueError):
            await change_invoice(invoice_id=invoice_id, session=session, user_id=user_id)

        assert session.in_transaction() is False

    async with session_pool() as session:
        invoice = await session.get(Invoice, invoice_id)
        assert invoice is not None
        assert invoice.status == status
        assert invoice.issue_version == version

@pytest.mark.parametrize('change_invoice_in_db',
                         [cancel_invoice_in_db,
                           revoke_invoice_in_db,
                            issue_invoice_in_db])
async def test_change_other_user_invoice(change_invoice_in_db, clean_tables, session_pool, bother_user, client):
    headersA, headersB = bother_user

    userA_response = await client.get('/auth/me', headers={'Authorization': headersA['Authorization']})
    assert userA_response.status_code == 200, userA_response.text
    userB_response = await client.get('/auth/me', headers={'Authorization': headersB['Authorization']})
    assert userB_response.status_code == 200, userB_response.text

    user_idA = userA_response.json()['id']
    user_idB = userB_response.json()['id']

    client_json = {
        "client_name": "Joe",
        "organization": "JoeCorp",
        "email": "joecorp@example.com",
        "client_status": "lead",
    }

    response = await client.post('/clients', json=client_json,
                                 headers={'Authorization': headersA['Authorization']})

    assert response.status_code == 201

    deal = await client.post('/deals', json={
        'name': 'Test work', 'amount': '1000.00',
        'client_id': response.json()['id'],
    }, headers={'Authorization': headersA['Authorization']})
    assert deal.status_code == 201, deal.text

    invoice_json = {
        "label": "invoiceA",
        "amount": "100",
        "deal_id": deal.json()["id"],
        "due_date": "2021-04-01",
    }

    invoice = await client.post('/invoices', json=invoice_json,
                                headers={'Authorization': headersA['Authorization']})

    assert invoice.status_code == 201

    invoice_id = invoice.json()['id']
    async with session_pool() as session:
        change_invoice = await change_invoice_in_db(user_id=user_idB, invoice_id=invoice_id, session=session)
        assert change_invoice is None

    async with session_pool() as session:
        invoice = await session.get(Invoice, invoice_id)
        assert invoice is not None
        assert invoice.status == InvoiceStatus.DRAFT
        assert invoice.issue_version == 0

async def test_rollback_after_record(clean_tables, session_pool, active_user, client, monkeypatch):
    headersA = active_user[0]

    userA_response = await client.get('/auth/me', headers={'Authorization': headersA['Authorization']})
    assert userA_response.status_code == 200, userA_response.text
    user_idA = userA_response.json()['id']

    client_json = {
        "client_name": "Joe",
        "organization": "JoeCorp",
        "email": "joecorp@example.com",
        "client_status": "lead",
    }

    response = await client.post('/clients', json=client_json,
                                 headers={'Authorization': headersA['Authorization']})

    assert response.status_code == 201

    deal = await client.post('/deals', json={
        'name': 'Test work', 'amount': '1000.00',
        'client_id': response.json()['id'],
    }, headers={'Authorization': headersA['Authorization']})
    assert deal.status_code == 201, deal.text

    invoice_json = {
        "label": "invoiceA",
        "amount": "100",
        "deal_id": deal.json()["id"],
        "due_date": "2021-04-01",
    }

    invoice = await client.post('/invoices', json=invoice_json,
                                headers={'Authorization': headersA['Authorization']})

    assert invoice.status_code == 201

    invoice_id = invoice.json()['id']

    async with session_pool() as session:
        async def mock_get_invoice_for_transition(user_id, invoice_id, session):
            get_invoice = await get_invoice_for_transition(user_id=user_id, invoice_id=invoice_id, session=session)
            assert get_invoice is not None
            cancel_invoice(get_invoice)
            await session.flush()
            raise RuntimeError("simulated failure")

        monkeypatch.setattr("backend.app.services.invoice.get_invoice_for_transition", mock_get_invoice_for_transition)
        with pytest.raises(RuntimeError):
            await cancel_invoice_in_db(user_id=user_idA, invoice_id=invoice_id, session=session)
        assert session.in_transaction() is False

    async with session_pool() as session:
        invoice = await session.get(Invoice, invoice_id)
        assert invoice.status == InvoiceStatus.DRAFT
        assert invoice.issue_version == 0

async def test_draft_to_issue(clean_tables, session_pool, client, active_user):
    headersA = active_user[0]

    userA_response = await client.get('/auth/me', headers={'Authorization': headersA['Authorization']})
    assert userA_response.status_code == 200, userA_response.text
    user_idA = userA_response.json()['id']

    client_json = {
        "client_name": "Joe",
        "organization": "JoeCorp",
        "email": "joecorp@example.com",
        "client_status": "lead",
    }

    response = await client.post('/clients', json=client_json,
                                 headers={'Authorization': headersA['Authorization']})

    assert response.status_code == 201

    deal = await client.post('/deals', json={
        'name': 'Test work', 'amount': '1000.00',
        'client_id': response.json()['id'],
    }, headers={'Authorization': headersA['Authorization']})
    assert deal.status_code == 201, deal.text

    invoice_json = {
        "label": "invoiceA",
        "amount": "100",
        "deal_id": deal.json()["id"],
        "due_date": "2021-04-01",
    }

    invoice = await client.post('/invoices', json=invoice_json,
                                headers={'Authorization': headersA['Authorization']})

    assert invoice.status_code == 201

    invoice_id = invoice.json()['id']

    async with session_pool() as session:
        complete_issue_invoice = await issue_invoice_in_db(user_id=user_idA, invoice_id=invoice_id, session=session)
        assert complete_issue_invoice is not None
        assert complete_issue_invoice.issue_version == 1

    async with session_pool() as session:
        complete_issue_invoice = await session.get(Invoice, invoice_id)
        assert complete_issue_invoice is not None
        assert complete_issue_invoice.status == InvoiceStatus.ISSUED
        assert complete_issue_invoice.issue_version == 1

    async with session_pool() as session:
        complete_revoke_invoice = await revoke_invoice_in_db(user_id=user_idA, invoice_id=invoice_id, session=session)
        assert complete_revoke_invoice is not None
        assert complete_revoke_invoice.issue_version == 1

    async with session_pool() as session:
        complete_issue_invoice = await session.get(Invoice, invoice_id)
        assert complete_issue_invoice is not None
        assert complete_issue_invoice.status == InvoiceStatus.DRAFT
        assert complete_issue_invoice.issue_version == 1

    async with session_pool() as session:
        complete_issue_invoice = await issue_invoice_in_db(user_id=user_idA, invoice_id=invoice_id, session=session)
        assert complete_issue_invoice is not None
        assert complete_issue_invoice.issue_version == 2

    async with session_pool() as session:
        complete_issue_invoice = await session.get(Invoice, invoice_id)
        assert complete_issue_invoice is not None
        assert complete_issue_invoice.status == InvoiceStatus.ISSUED
        assert complete_issue_invoice.issue_version == 2


@pytest.mark.parametrize('change_invoice', [issue_invoice_in_db, revoke_invoice_in_db],
                         ids=['issue', 'revoke'])
@pytest.mark.parametrize('initial_status', [InvoiceStatus.PAID, InvoiceStatus.CANCELLED],
                         ids=['paid', 'cancelled'])
async def test_issue_and_revoke_reject_terminal_status(
        change_invoice, initial_status, clean_tables, session_pool, active_user, client):
    headers = active_user[0]
    me = await client.get('/auth/me', headers=headers)
    assert me.status_code == 200, me.text
    user_id = me.json()['id']

    client_response = await client.post('/clients', json={
        'client_name': 'Joe',
        'organization': 'JoeCorp',
        'email': 'joecorp@example.com',
        'client_status': 'lead',
    }, headers=headers)
    assert client_response.status_code == 201, client_response.text

    deal_response = await client.post('/deals', json={
        'name': 'Test work',
        'amount': '1000.00',
        'client_id': client_response.json()['id'],
    }, headers=headers)
    assert deal_response.status_code == 201, deal_response.text

    invoice_response = await client.post('/invoices', json={
        'label': 'invoiceA',
        'amount': '100',
        'deal_id': deal_response.json()['id'],
        'due_date': '2021-04-01',
    }, headers=headers)
    assert invoice_response.status_code == 201, invoice_response.text
    invoice_id = invoice_response.json()['id']
    initial_version = 3

    # Prepare and commit the starting state before calling the service.
    async with session_pool() as session:
        async with session.begin():
            invoice = await session.get(Invoice, invoice_id)
            assert invoice is not None
            invoice.status = initial_status
            invoice.issue_version = initial_version
            if initial_status == InvoiceStatus.PAID:
                invoice.is_paid = True
                invoice.paid_at = datetime.now(timezone.utc)

    async with session_pool() as session:
        with pytest.raises(ValueError):
            await change_invoice(invoice_id=invoice_id, user_id=user_id, session=session)
        assert session.in_transaction() is False

    # A new session checks persisted data, not the previous identity map.
    async with session_pool() as session:
        invoice = await session.get(Invoice, invoice_id)
        assert invoice is not None
        assert invoice.status == initial_status
        assert invoice.issue_version == initial_version
