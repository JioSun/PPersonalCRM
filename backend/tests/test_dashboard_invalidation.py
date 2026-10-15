import pytest


@pytest.mark.parametrize('action', [
    'client_create', 'client_patch', 'deal_create', 'deal_patch',
    'invoice_create', 'invoice_patch', 'invoice_delete',
    'issue', 'revoke', 'cancel', 'rejected_issue', 'foreign_patch',
])
async def test_dashboard_invalidation_http(action, bother_user, client, redis_session):
    headers, other_headers = bother_user
    me = await client.get('/auth/me', headers=headers)
    assert me.status_code == 200, me.text
    key = f"dashboard:{me.json()['id']}"
    other = await client.get('/auth/me', headers=other_headers)
    assert other.status_code == 200, other.text
    other_key = f"dashboard:{other.json()['id']}"
    customer_data = {
        'client_name': 'Joe', 'organization': 'JoeCorp',
        'email': 'joecorp@example.com', 'client_status': 'lead',
    }
    customer = await client.post('/clients', json=customer_data, headers=headers)
    assert customer.status_code == 201, customer.text
    client_id = customer.json()['id']
    deal_data = {'name': 'Cache work', 'amount': '100.00', 'client_id': client_id}
    deal = await client.post('/deals', json=deal_data, headers=headers)
    assert deal.status_code == 201, deal.text
    deal_id = deal.json()['id']
    invoice_data = {
        'label': 'Cache invoice', 'amount': '40.00',
        'due_date': '2000-01-01', 'deal_id': deal_id,
    }
    invoice = await client.post('/invoices', json=invoice_data, headers=headers)
    assert invoice.status_code == 201, invoice.text
    invoice_id = invoice.json()['id']
    if action in ('revoke', 'cancel', 'rejected_issue'):
        response = await client.post(f'/invoices/{invoice_id}/issue', headers=headers)
        assert response.status_code == 200, response.text

    before = await client.get('/dashboard', headers=headers)
    assert before.status_code == 200, before.text
    original_cache = await redis_session.get(key)
    assert original_cache is not None
    await redis_session.set(other_key, 'other cached summary')

    if action == 'client_create':
        response = await client.post('/clients', json={**customer_data, 'client_name': 'New'}, headers=headers)
    elif action == 'client_patch':
        response = await client.patch(f'/clients/{client_id}', json={'client_name': 'Renamed'}, headers=headers)
    elif action == 'deal_create':
        response = await client.post('/deals', json={**deal_data, 'name': 'New deal'}, headers=headers)
    elif action == 'deal_patch':
        response = await client.patch(f'/deals/{deal_id}', json={'amount': '120.00'}, headers=headers)
    elif action == 'invoice_create':
        response = await client.post('/invoices', json={**invoice_data, 'label': 'New invoice'}, headers=headers)
    elif action == 'invoice_patch':
        response = await client.patch(f'/invoices/{invoice_id}', json={'amount': '45.00'}, headers=headers)
    elif action == 'invoice_delete':
        response = await client.delete(f'/invoices/{invoice_id}', headers=headers)
    elif action == 'foreign_patch':
        response = await client.patch(f'/deals/{deal_id}', json={'amount': '120.00'}, headers=other_headers)
    else:
        transition = 'issue' if action == 'rejected_issue' else action
        response = await client.post(f'/invoices/{invoice_id}/{transition}', headers=headers)

    expected_code = 200
    if action.endswith('_create'):
        expected_code = 201
    elif action == 'invoice_delete':
        expected_code = 204
    elif action == 'rejected_issue':
        expected_code = 409
    elif action == 'foreign_patch':
        expected_code = 404
    assert response.status_code == expected_code, response.text
    assert await redis_session.get(other_key) == 'other cached summary'
    if action in ('rejected_issue', 'foreign_patch'):
        assert await redis_session.get(key) == original_cache
    else:
        assert await redis_session.get(key) is None
    fresh = await client.get('/dashboard', headers=headers)
    assert fresh.status_code == 200, fresh.text
    assert await redis_session.get(key) is not None
    body = fresh.json()
    if action == 'client_create':
        assert body['clients_count'] == 2
    elif action == 'client_patch':
        assert body['clients_summary'][0]['client_name'] == 'Renamed'
    elif action == 'deal_create':
        assert body['deals_by_status']['new'] == 2
    elif action == 'deal_patch':
        assert body['clients_summary'][0]['total_amount'] == '120.00'
    elif action == 'issue':
        assert body['unpaid_amount'] == '40.00'
        assert body['overdue_count'] == 1
    elif action in ('revoke', 'cancel'):
        assert body['unpaid_amount'] == '0'
        assert body['overdue_count'] == 0
    elif action in ('rejected_issue', 'foreign_patch'):
        assert body == before.json()
