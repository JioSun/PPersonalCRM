from datetime import date
from decimal import Decimal

import pytest
import pytest_asyncio
from sqlalchemy import select

from backend.app.models.constants import InvoiceStatus
from backend.app.models.database_models import Client, Deal, Invoice, User


@pytest_asyncio.fixture
async def invoice_links(async_session, active_user, other_active_user):
    owner = await async_session.scalar(
        select(User).where(User.email == 'testuser@xample.com')
    )
    outsider = await async_session.scalar(
        select(User).where(User.email == 'testuser1@xample.com')
    )
    assert owner is not None and outsider is not None
    clients = {}
    deals = {}
    for key, user in [('a', owner), ('b', owner), ('foreign', outsider)]:
        customer = Client(client_name=f'Client {key}', user_id=user.id)
        async_session.add(customer)
        await async_session.flush()
        deal = Deal(
            name=f'Deal {key}',
            amount=Decimal('1000'),
            client_id=customer.id,
            user_id=user.id,
        )
        async_session.add(deal)
        await async_session.flush()
        clients[key] = customer.id
        deals[key] = deal.id
    invoices = {}
    for key, user, customer, deal in [
        ('linked', owner, 'a', deals['a']),
        ('foreign', outsider, 'foreign', deals['foreign']),
    ]:
        invoice = Invoice(
            label=f'Invoice {key}',
            number=f'TEST-{key}',
            amount=Decimal('100'),
            due_date=date(2030, 1, 1),
            user_id=user.id,
            client_id=clients[customer],
            deal_id=deal,
            status=InvoiceStatus.DRAFT,
        )
        async_session.add(invoice)
        await async_session.flush()
        invoices[key] = invoice.id
    await async_session.commit()
    return {
        'clients': clients,
        'deals': deals,
        'invoices': invoices,
        'headers': active_user[0],
        'foreign_headers': other_active_user,
    }


async def read_invoice(client, data, key):
    headers = data['foreign_headers'] if key == 'foreign' else data['headers']
    response = await client.get(f'/invoices/{data["invoices"][key]}', headers=headers)
    assert response.status_code == 200, response.text
    return response.json()


async def verify_patch(client, async_session, data, key, payload, expected_status):
    before = await read_invoice(client, data, key)
    response = await client.patch(
        f'/invoices/{data["invoices"][key]}', headers=data['headers'], json=payload
    )
    # Discard ORM identity-map state: the GET must read persisted values.
    await async_session.rollback()
    async_session.expire_all()
    after = await read_invoice(client, data, key)
    if expected_status != 200:
        assert after == before, 'Rejected PATCH changed the stored invoice'
    assert response.status_code == expected_status, response.text
    if expected_status == 200:
        assert response.json() == after
    return before, after


async def test_patch_draft_details_preserves_links(
    client, async_session, invoice_links
):
    """Название, сумма и срок меняются; клиент и сделка остаются прежними."""
    payload = {'label': 'Updated label', 'amount': '150.00', 'due_date': '2030-02-01'}
    before, after = await verify_patch(
        client, async_session, invoice_links, 'linked', payload, 200
    )
    assert after['label'] == payload['label']
    assert Decimal(after['amount']) == Decimal('150.00')
    assert after['due_date'] == payload['due_date']
    for field in ('client_id', 'deal_id', 'status', 'number', 'paid_at', 'created_at'):
        assert after[field] == before[field]


async def test_patch_empty_preserves_links(client, async_session, invoice_links):
    before, after = await verify_patch(
        client, async_session, invoice_links, 'linked', {}, 200
    )
    for field in ('client_id', 'deal_id', 'label', 'amount', 'due_date', 'status'):
        assert after[field] == before[field]


@pytest.mark.parametrize('field', ['client_id', 'deal_id'])
@pytest.mark.parametrize('value_kind', ['same', 'other', 'foreign', 'missing', 'null'])
async def test_patch_links_are_immutable(
    client, async_session, invoice_links, field, value_kind
):
    """Даже прежнее значение или null запрещены: поля отсутствуют в PATCH-контракте."""
    objects = invoice_links['clients' if field == 'client_id' else 'deals']
    values = {
        'same': objects['a'],
        'other': objects['b'],
        'foreign': objects['foreign'],
        'missing': '00000000000000000000000000',
        'null': None,
    }
    await verify_patch(
        client,
        async_session,
        invoice_links,
        'linked',
        {field: values[value_kind], 'label': 'Must not persist'},
        422,
    )


async def test_patch_cannot_move_invoice_with_matching_pair(
    client, async_session, invoice_links
):
    """Даже согласованная пара другого своего клиента и сделки не разрешает перенос."""
    await verify_patch(
        client,
        async_session,
        invoice_links,
        'linked',
        {
            'client_id': invoice_links['clients']['b'],
            'deal_id': invoice_links['deals']['b'],
            'label': 'Must not persist',
        },
        422,
    )


async def test_patch_foreign_invoice_is_not_found(client, async_session, invoice_links):
    await verify_patch(
        client,
        async_session,
        invoice_links,
        'foreign',
        {'label': 'Must not persist'},
        404,
    )


async def test_patch_missing_invoice_is_not_found(client, invoice_links):
    response = await client.patch(
        '/invoices/00000000000000000000000000',
        headers=invoice_links['headers'],
        json={'label': 'Must not persist'},
    )
    assert response.status_code == 404, response.text


# Currently the enum still has SENT/OVERDUE. Cover every non-draft value;
# ISSUED is automatically covered after the domain enum is migrated.
@pytest.mark.parametrize(
    'invoice_status', [s for s in InvoiceStatus if s != InvoiceStatus.DRAFT]
)
async def test_patch_non_draft_is_rejected(
    client, async_session, invoice_links, invoice_status
):
    invoice = await async_session.get(Invoice, invoice_links['invoices']['linked'])
    invoice.status = invoice_status
    await async_session.commit()
    await verify_patch(
        client,
        async_session,
        invoice_links,
        'linked',
        {'label': 'Must not persist'},
        409,
    )


@pytest.mark.parametrize(
    'field,value',
    [
        ('status', 'draft'),
        ('paid_at', '2030-01-01T00:00:00Z'),
        ('number', 'FORGED'),
        ('user_id', 'forged-owner'),
    ],
)
async def test_patch_server_fields_are_forbidden(
    client, async_session, invoice_links, field, value
):
    await verify_patch(
        client,
        async_session,
        invoice_links,
        'linked',
        {field: value, 'label': 'Must not persist'},
        422,
    )


async def test_delete_draft(client, async_session, invoice_links):
    invoice_id = invoice_links['invoices']['linked']
    response = await client.delete(
        f'/invoices/{invoice_id}', headers=invoice_links['headers']
    )
    assert response.status_code == 204, response.text
    assert response.content == b''
    await async_session.rollback()
    async_session.expire_all()
    assert await async_session.get(Invoice, invoice_id) is None
    response = await client.get(
        f'/invoices/{invoice_id}', headers=invoice_links['headers']
    )
    assert response.status_code == 404, response.text
    assert await async_session.get(Deal, invoice_links['deals']['a']) is not None
    assert await async_session.get(Client, invoice_links['clients']['a']) is not None


@pytest.mark.parametrize(
    'invoice_status', [s for s in InvoiceStatus if s != InvoiceStatus.DRAFT]
)
async def test_delete_non_draft_is_rejected(
    client, async_session, invoice_links, invoice_status
):
    invoice_id = invoice_links['invoices']['linked']
    invoice = await async_session.get(Invoice, invoice_id)
    invoice.status = invoice_status
    await async_session.commit()
    before = await read_invoice(client, invoice_links, 'linked')
    response = await client.delete(
        f'/invoices/{invoice_id}', headers=invoice_links['headers']
    )
    assert response.status_code == 409, response.text
    await async_session.rollback()
    async_session.expire_all()
    assert await read_invoice(client, invoice_links, 'linked') == before


async def test_delete_foreign_invoice_is_not_found(
    client, async_session, invoice_links
):
    before = await read_invoice(client, invoice_links, 'foreign')
    response = await client.delete(
        f'/invoices/{invoice_links["invoices"]["foreign"]}',
        headers=invoice_links['headers'],
    )
    assert response.status_code == 404, response.text
    await async_session.rollback()
    async_session.expire_all()
    assert await read_invoice(client, invoice_links, 'foreign') == before


async def test_delete_missing_invoice_is_not_found(client, invoice_links):
    response = await client.delete(
        '/invoices/00000000000000000000000000', headers=invoice_links['headers']
    )
    assert response.status_code == 404, response.text


async def test_create_invoice_derives_client_from_own_deal(
    client, async_session, invoice_links
):
    """Клиент не передаётся: сервер берёт его из своей сделки и создаёт DRAFT."""
    payload = {
        'label': 'New work invoice',
        'amount': '123.45',
        'due_date': '2030-03-01',
        'deal_id': invoice_links['deals']['a'],
    }
    response = await client.post(
        '/invoices', headers=invoice_links['headers'], json=payload
    )
    assert response.status_code == 201, response.text
    created = response.json()
    assert created['client_id'] == invoice_links['clients']['a']
    assert created['deal_id'] == payload['deal_id']
    assert created['status'] == InvoiceStatus.DRAFT.value
    assert created['paid_at'] is None
    assert created['currency'] == 'USD'
    assert created['label'] == payload['label']
    assert Decimal(created['amount']) == Decimal(payload['amount'])
    assert created['due_date'] == payload['due_date']
    await async_session.rollback()
    async_session.expire_all()
    saved = await client.get(
        f'/invoices/{created["id"]}', headers=invoice_links['headers']
    )
    assert saved.status_code == 200, saved.text
    assert saved.json() == created
    invoice = await async_session.get(Invoice, created['id'])
    deal = await async_session.get(Deal, payload['deal_id'])
    assert invoice.user_id == deal.user_id


@pytest.mark.parametrize('deal_kind', ['foreign', 'missing'])
async def test_create_invoice_rejects_unavailable_deal(
    client, async_session, invoice_links, deal_kind
):
    """Чужая и отсутствующая сделки дают одинаковый 404 и не создают запись."""
    before = set((await async_session.scalars(select(Invoice.id))).all())
    deal_id = (
        invoice_links['deals']['foreign']
        if deal_kind == 'foreign'
        else '00000000000000000000000000'
    )
    response = await client.post(
        '/invoices',
        headers=invoice_links['headers'],
        json={
            'label': 'Must not be created',
            'amount': '100.00',
            'due_date': '2030-03-01',
            'deal_id': deal_id,
        },
    )
    assert response.status_code == 404, response.text
    await async_session.rollback()
    async_session.expire_all()
    after = set((await async_session.scalars(select(Invoice.id))).all())
    assert after == before
