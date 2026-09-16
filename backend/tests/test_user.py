async def test_register(client):
    response = await client.post('/auth/register', json={
      "email": "gresges@xample.com",
      "full_name": "asd",
      "username": "asdasd",
      "password": "JOOPPAds23123"
    })

    assert response.status_code == 200

    response = await client.post('/auth/register', json={
        "email": "gresges@xample.com",
        "full_name": "asd",
        "username": "asdasd",
        "password": "JOOPPAds23123"
    })
    assert response.status_code == 400

async def test_client_works(client, active_user):
    client_json ={
      "client_name": "Joe",
      "organization": "JoeCorp",
      "email": "joecorp@example.com",
      "client_status": "lead",
    }
    response = await client.post('/clients', json=client_json)

    assert response.status_code == 401

async def test_client_refresh(client, active_user):
    client_json = {
        "client_name": "Joe",
        "organization": "JoeCorp",
        "email": "joecorp@example.com",
        "client_status": "lead",
    }

    response = active_user[1]

    print(response.json())
    headers = {"Authorization": f"Bearer {response.json()['refresh_token']}"}

    response = await client.post('/clients', json=client_json, headers={'Authorization': headers['Authorization']})

    assert response.status_code == 401

async def test_users_reading(active_user, other_active_user, client):
    client_json_a = {
        "client_name": "Joe",
        "organization": "JoeCorp",
        "email": "joecorp@example.com",
        "client_status": "lead",
    }

    client_json_b = {
        "client_name": "JoeB",
        "organization": "JoeCorpB",
        "email": "joecorpB@example.com",
        "client_status": "lead",
    }
    active_user = active_user[0]

    client_a = await client.post('/clients', json=client_json_a, headers={'Authorization': active_user['Authorization']})

    assert client_a.status_code == 201

    client_b = await client.post('/clients', json=client_json_b, headers={'Authorization': other_active_user['Authorization']})

    assert client_b.status_code == 201

    response_a = await client.get(f'/clients/{client_a.json().get('id')}', headers={'Authorization': other_active_user['Authorization']})

    assert response_a.status_code == 404

    response_b = await client.get(f'/clients/{client_b.json().get('id')}', headers={'Authorization': active_user['Authorization']})

    assert response_b.status_code == 404

async def test_two_email_reg(client):
    json = {
        "email": "testuser@xample.com",
        "full_name": "User Test",
        "username": "UTest",
        "password": "Kill2896"
    }
    response1 = await client.post("/auth/register", json=json)

    assert response1.status_code == 200

    response2 = await client.post("/auth/register", json=json)

    assert response2.status_code == 400

async def test_create_invoice_with_other_user(client, active_user, other_active_user):
    client_json_a = {
        "client_name": "Joe",
        "organization": "JoeCorp",
        "email": "joecorp@example.com",
        "client_status": "lead",
    }

    client_json_b = {
        "client_name": "JoeB",
        "organization": "JoeCorpB",
        "email": "joecorpB@example.com",
        "client_status": "lead",
    }




    active_user = active_user[0]

    client_a = await client.post('/clients', json=client_json_a,
                                 headers={'Authorization': active_user['Authorization']})

    assert client_a.status_code == 201

    client_b = await client.post('/clients', json=client_json_b,
                                 headers={'Authorization': other_active_user['Authorization']})

    assert client_b.status_code == 201

    deal_json_a = {
         "name": "dealA",
         "client_id": client_b.json().get('id'),
     }

    deal_json_b = {
         "name": "dealB",
         "client_id": client_b.json().get('id'),
    }

    assert client_b.status_code == 201

    deal_a = await client.post(f'/deals', json=deal_json_a, headers={'Authorization': active_user['Authorization']})

    assert deal_a.status_code == 404

    deal_b = await client.post(f'/deals', json=deal_json_b, headers={'Authorization': other_active_user['Authorization']})

    assert deal_b.status_code == 201

    invoice_a = {
        "label": "invoiceA",
        "deal_id": deal_b.json().get('id'),
        "client_id": client_b.json().get('id')
    }

    invoice_a = await client.post(f'/invoices', json=invoice_a, headers={'Authorization': active_user['Authorization']})

    assert invoice_a.status_code == 401