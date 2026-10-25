import json
from decimal import Decimal

import pytest

from ..app.models.constants import ClientStatus, DealStatus
from ..app.models.database_models import Client, Deal


@pytest.mark.parametrize(
    'scenario', ['empty', 'clients_only', 'sparse', 'all_statuses']
)
async def test_dashboard_counts_http(
    scenario, bother_user, client, session_pool, redis_session
):
    headers, other_headers = bother_user
    me = await client.get('/auth/me', headers=headers)
    assert me.status_code == 200, me.text
    user_id = me.json()['id']
    other_me = await client.get('/auth/me', headers=other_headers)
    assert other_me.status_code == 200, other_me.text
    other_id = other_me.json()['id']

    expected_clients = 0 if scenario == 'empty' else 4
    expected_deals = {status.value: 0 for status in DealStatus}
    if scenario == 'sparse':
        expected_deals['new'] = 3
        expected_deals['completed'] = 1
    elif scenario == 'all_statuses':
        expected_deals = {
            'new': 1,
            'in_progress': 2,
            'on_review': 3,
            'completed': 4,
            'cancelled': 5,
        }

    async with session_pool() as session:
        async with session.begin():
            own_clients = []
            for index, status in enumerate(ClientStatus):
                if scenario == 'empty':
                    break
                customer = Client(
                    client_name=f'Own client {index}',
                    user_id=user_id,
                    client_status=status,
                )
                session.add(customer)
                own_clients.append(customer)
            other_client = Client(client_name='Other client', user_id=other_id)
            session.add(other_client)
            await session.flush()

            # У первого клиента несколько сделок, остальные остаются без сделок.
            for status, count in expected_deals.items():
                for index in range(count):
                    session.add(
                        Deal(
                            name=f'{status} {index}',
                            amount=Decimal('100.00'),
                            user_id=user_id,
                            client_id=own_clients[0].id,
                            status=DealStatus(status),
                        )
                    )
            # Чужие записи есть даже в сценарии пустой сводки владельца.
            for status in DealStatus:
                session.add(
                    Deal(
                        name=f'Other {status.value}',
                        amount=Decimal('900.00'),
                        user_id=other_id,
                        client_id=other_client.id,
                        status=status,
                    )
                )

    await redis_session.delete(f'dashboard:{user_id}')
    response = await client.get('/dashboard', headers=headers)
    assert response.status_code == 200, response.text
    body = response.json()
    assert type(body['clients_count']) is int
    assert body['clients_count'] == expected_clients
    assert body['deals_by_status'] == expected_deals
    assert all(type(count) is int for count in body['deals_by_status'].values())
    assert {
        'clients_summary',
        'overdue_invoice',
        'paid_amount',
        'unpaid_amount',
        'overdue_amount',
        'overdue_count',
    } <= body.keys()

    cached_json = await redis_session.get(f'dashboard:{user_id}')
    assert cached_json is not None
    assert json.loads(cached_json) == body
    cached = await client.get('/dashboard', headers=headers)
    assert cached.status_code == 200, cached.text
    assert cached.json() == body

    # Отдельный ответ и ключ кэша второго пользователя.
    await redis_session.delete(f'dashboard:{other_id}')
    other_response = await client.get('/dashboard', headers=other_headers)
    assert other_response.status_code == 200, other_response.text
    assert other_response.json()['clients_count'] == 1
    assert other_response.json()['deals_by_status'] == {
        status.value: 1 for status in DealStatus
    }
    assert await redis_session.get(f'dashboard:{user_id}') == cached_json
