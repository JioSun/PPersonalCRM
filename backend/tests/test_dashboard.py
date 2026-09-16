async def test_dashboard_working(client, active_user):
    active_user = active_user[0]
    response = await client.get('/dashboard', headers={'Authorization': active_user['Authorization']})

    assert response.status_code == 200
    data = response.json()
    assert data["clients_summary"] == []
    assert data["overdue_invoice"] == []
