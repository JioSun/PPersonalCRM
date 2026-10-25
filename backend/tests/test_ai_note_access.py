from unittest.mock import AsyncMock

import pytest


@pytest.mark.parametrize(
    'scenario, expected_status',
    [
        ('foreign_client', 404),
        ('missing_client', 404),
        ('blank_note', 422),
        ('anonymous', 401),
    ],
)
async def test_ai_note_rejected_before_provider(
    scenario, expected_status, client, active_user, other_active_user, monkeypatch
):
    formatter = AsyncMock(return_value=None)
    monkeypatch.setattr('backend.app.api.routes.clients.note_formatter', formatter)
    owner_headers = (
        other_active_user if scenario == 'foreign_client' else active_user[0]
    )
    created = await client.post(
        '/clients',
        headers=owner_headers,
        json={
            'client_name': 'Notes recipient',
            'email': 'notes@example.com',
        },
    )
    assert created.status_code == 201, created.text
    client_id = created.json()['id']
    if scenario == 'missing_client':
        client_id = '00000000000000000000000000'
    note = 'Обсудили разработку сайта и подготовку предложения для клиента.'
    if scenario == 'blank_note':
        note = ' ' * 40
    headers = {} if scenario == 'anonymous' else active_user[0]
    response = await client.post(
        f'/clients/{client_id}/notes',
        headers=headers,
        json=note,
    )
    assert response.status_code == expected_status, response.text
    formatter.assert_not_called()
