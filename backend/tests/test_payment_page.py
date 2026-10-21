async def test_payment_page_is_public_html(client):
    response = await client.get('/pay/nonexistent-invoice/invalid-token')

    assert response.status_code == 200, response.text
    assert 'text/html' in response.headers['content-type']
    assert 'реальные средства не списываются' in response.text
