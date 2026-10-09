"""Stage 2.4: persisted API values and database constraints (no status transitions)."""
from decimal import Decimal

import pytest
import pytest_asyncio
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError


@pytest_asyncio.fixture
async def records(client, active_user):
    headers = active_user[0]
    response = await client.post('/clients', headers=headers, json={
        'client_name': 'Persistence client', 'email': 'persist@example.com',
    })
    assert response.status_code == 201, response.text
    customer = response.json()['id']
    deal_data = {
        'name': 'Website', 'amount': '1234.56', 'client_id': customer,
        'deadline': '2030-06-15', 'notes': 'All requested fields',
    }
    response = await client.post('/deals', headers=headers, json=deal_data)
    assert response.status_code == 201, response.text
    deal = response.json()['id']
    invoice_data = {
        'label': 'First milestone', 'amount': '123.45',
        'due_date': '2030-06-01', 'deal_id': deal,
    }
    response = await client.post('/invoices', headers=headers, json=invoice_data)
    assert response.status_code == 201, response.text
    return headers, customer, deal, response.json()['id'], deal_data, invoice_data


@pytest.mark.parametrize('resource', ['deals', 'invoices'])
async def test_post_get_all_fields(client, records, resource):
    headers, customer, deal, invoice, deal_data, invoice_data = records
    identifier, expected = (deal, deal_data) if resource == 'deals' else (invoice, invoice_data)
    response = await client.get(f'/{resource}/{identifier}', headers=headers)
    assert response.status_code == 200, response.text
    actual = response.json()
    for key, value in expected.items():
        assert (Decimal(actual[key]) == Decimal(value)) if key == 'amount' else actual[key] == value
    assert actual['client_id'] == customer
    assert actual['currency'] == 'USD'


@pytest.mark.parametrize(('resource', 'patch'), [
    ('deals', {'name': 'Updated name'}),
    ('deals', {'amount': '2000.01'}),
    ('deals', {'notes': None}),
    ('deals', {'deadline': None}),
    ('invoices', {'label': 'Updated label'}),
    ('invoices', {'amount': '99.99'}),
    ('invoices', {'due_date': '2030-07-01'}),
])
async def test_patch_preserves_other_fields(client, records, resource, patch):
    headers, _, deal, invoice, *_ = records
    url = f'/{resource}/{deal if resource == "deals" else invoice}'
    before = await client.get(url, headers=headers)
    assert before.status_code == 200, before.text
    response = await client.patch(url, headers=headers, json=patch)
    assert response.status_code == 200, response.text
    after = await client.get(url, headers=headers)
    assert after.status_code == 200, after.text
    expected = before.json() | patch
    actual = after.json()
    expected.pop('updated_at')
    actual.pop('updated_at')
    expected['amount'] = Decimal(expected['amount'])
    actual['amount'] = Decimal(actual['amount'])
    assert actual == expected


@pytest.mark.parametrize('resource', ['deals', 'invoices'])
@pytest.mark.parametrize('amount', ['-1', None, '1.234'])
async def test_invalid_patch_leaves_record_unchanged(client, records, resource, amount):
    headers, _, deal, invoice, *_ = records
    url = f'/{resource}/{deal if resource == "deals" else invoice}'
    before = await client.get(url, headers=headers)
    assert before.status_code == 200, before.text
    patch = {'amount': amount, 'name' if resource == 'deals' else 'label': 'Must not persist'}
    response = await client.patch(url, headers=headers, json=patch)
    assert response.status_code == 422, response.text
    after = await client.get(url, headers=headers)
    assert after.status_code == 200, after.text
    assert after.json() == before.json()


@pytest.mark.parametrize(('table', 'column', 'value', 'sqlstate'), [
    ('invoices', 'amount', '0', '23514'),
    ('invoices', 'amount', '-1', '23514'),
    ('deals', 'amount', '-1', '23514'),
    ('invoices', 'currency', 'EUR', '23514'),
    ('deals', 'currency', 'EUR', '23514'),
    ('invoices', 'label', '', '23514'),
    ('invoices', 'label', '   ', '23514'),
    ('deals', 'name', '', '23514'),
    ('deals', 'name', '   ', '23514'),
    ('invoices', 'label', 'x' * 51, '22001'),
    ('deals', 'name', 'x' * 51, '22001'),
    ('deals', 'notes', 'x' * 5001, '22001'),
    ('invoices', 'deal_id', None, '23502'),
    ('invoices', 'due_date', None, '23502'),
])
async def test_database_rejects_invalid_values(records, session_pool, table, column, value, sqlstate):
    _, _, deal, invoice, *_ = records
    if column == 'amount':
        value = Decimal(value)
    # Identifiers come only from the fixed parameter list, never request data.
    async with session_pool() as session:
        with pytest.raises(DBAPIError) as exc:
            await session.execute(text(f'UPDATE {table} SET {column} = :value WHERE id = :id'),
                                  {'value': value, 'id': deal if table == 'deals' else invoice})
        assert exc.value.orig.sqlstate == sqlstate
        await session.rollback()


async def test_database_accepts_zero_deal(records, session_pool):
    async with session_pool() as session:
        result = await session.execute(text('UPDATE deals SET amount = 0 WHERE id = :id RETURNING amount'),
                                       {'id': records[2]})
        assert result.scalar_one() == Decimal('0')
        await session.rollback()
