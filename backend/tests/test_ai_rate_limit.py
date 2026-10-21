from unittest.mock import AsyncMock

import asyncio


async def test_ai_limit_is_per_user_and_blocks_provider(
        client, active_user, other_active_user, monkeypatch):
    formatter = AsyncMock(return_value=None)
    monkeypatch.setattr('backend.app.api.routes.clients.note_formatter', formatter)
    headers = active_user[0]
    created = await client.post('/clients', headers=headers, json={
        'client_name': 'AI limit client',
    })
    assert created.status_code == 201
    client_id = created.json()['id']
    note = 'Обсудили разработку сайта и стоимость выполнения работ.'
    # Пустой ответ провайдера не отменяет уже выполненное обращение к нему.
    for _ in range(5):
        response = await client.post(
            f'/clients/{client_id}/notes', headers=headers, json=note,
        )
        assert response.status_code == 502, response.text
    assert formatter.await_count == 5
    blocked = await client.post(
        f'/clients/{client_id}/notes', headers=headers, json=note,
    )
    assert blocked.status_code == 429, blocked.text
    assert formatter.await_count == 5
    # Обычный API и другой пользователь с того же IP остаются доступны.
    ordinary = await client.get(f'/clients/{client_id}', headers=headers)
    assert ordinary.status_code == 200
    other = await client.post('/clients', headers=other_active_user, json={
        'client_name': 'Other AI limit client',
    })
    assert other.status_code == 201
    response = await client.post(
        f"/clients/{other.json()['id']}/notes", headers=other_active_user, json=note,
    )
    assert response.status_code == 502, response.text
    assert formatter.await_count == 6


async def test_invalid_requests_do_not_spend_ai_quota(
        client, active_user, other_active_user, monkeypatch):
    formatter = AsyncMock(return_value=None)
    monkeypatch.setattr('backend.app.api.routes.clients.note_formatter', formatter)
    headers = active_user[0]
    own = await client.post('/clients', headers=headers,
                            json={'client_name': 'Own quota client'})
    foreign = await client.post('/clients', headers=other_active_user,
                                json={'client_name': 'Foreign quota client'})
    assert own.status_code == foreign.status_code == 201
    own_url = f"/clients/{own.json()['id']}/notes"
    note = 'Обсудили разработку сайта и стоимость выполнения работ.'
    for url, body, expected in [
        (own_url, 'short', 422),
        (own_url, ' ' * 40, 422),
        (f"/clients/{foreign.json()['id']}/notes", note, 404),
        ('/clients/missing-client/notes', note, 404),
    ]:
        response = await client.post(url, headers=headers, json=body)
        assert response.status_code == expected, response.text
    formatter.assert_not_awaited()
    for _ in range(5):
        response = await client.post(own_url, headers=headers, json=note)
        assert response.status_code == 502, response.text
    response = await client.post(own_url, headers=headers, json=note)
    assert response.status_code == 429
    assert formatter.await_count == 5


async def test_clients_share_window_and_denial_does_not_extend_it(
        client, active_user, redis_session, monkeypatch):
    formatter = AsyncMock(return_value=None)
    monkeypatch.setattr('backend.app.api.routes.clients.note_formatter', formatter)
    headers = active_user[0]
    me = await client.get('/auth/me', headers=headers)
    assert me.status_code == 200
    key = f"ratelimit:ai:{me.json()['id']}"
    urls = []
    for name in ('First quota client', 'Second quota client'):
        created = await client.post('/clients', headers=headers,
                                    json={'client_name': name})
        assert created.status_code == 201
        urls.append(f"/clients/{created.json()['id']}/notes")
    note = 'Обсудили разработку сайта и стоимость выполнения работ.'
    for index in range(5):
        response = await client.post(urls[index % 2], headers=headers, json=note)
        assert response.status_code == 502, response.text
    assert 0 < await redis_session.pttl(key) <= 60000
    # Укорачиваем реальное окно Redis без ожидания целой минуты.
    await redis_session.pexpire(key, 10000)
    before = await redis_session.pttl(key)
    blocked = await client.post(urls[1], headers=headers, json=note)
    assert blocked.status_code == 429
    assert 0 < await redis_session.pttl(key) <= before
    assert formatter.await_count == 5
    await redis_session.pexpire(key, 1)
    await asyncio.sleep(0.02)
    assert not await redis_session.exists(key)
    response = await client.post(urls[0], headers=headers, json=note)
    assert response.status_code == 502, response.text
    assert formatter.await_count == 6
    assert 0 < await redis_session.pttl(key) <= 60000
