from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock
from urllib.parse import urlsplit

import pytest
from aiosmtplib.errors import (
    SMTPConnectTimeoutError,
    SMTPException,
    SMTPReadTimeoutError,
    SMTPTimeoutError,
)
from sqlalchemy import select

from ..app.core.config import settings
from ..app.models.database_models import Invoice, Token


@pytest.mark.parametrize(
    'scenario, expected_status',
    [
        ('success', 200),
        ('wrong_token', 409),
        ('wrong_client', 404),
        ('foreign_invoice', 404),
        ('missing_email', 404),
        ('anonymous', 401),
        ('smtp_failure', 502),
        ('timeout', 502),
        ('connect_timeout', 502),
        ('read_timeout', 502),
    ],
)
async def test_send_email(
    scenario,
    expected_status,
    client,
    monkeypatch,
    active_user,
    other_active_user,
    session_pool,
):
    smtp_send = AsyncMock()

    monkeypatch.setattr(
        'backend.app.api.routes.invoices.aiosmtplib.send',
        smtp_send,
    )

    headers = active_user[0]
    response = await client.post(
        '/clients',
        headers=headers,
        json={
            'client_name': 'Recipient client',
            'email': None if scenario == 'missing_email' else 'recipient@example.com',
        },
    )
    assert response.status_code == 201, response.text
    customer = response.json()['id']
    deal_data = {
        'name': 'Website',
        'amount': '1234.56',
        'client_id': customer,
        'deadline': '2030-06-15',
        'notes': 'All requested fields',
    }
    response = await client.post('/deals', headers=headers, json=deal_data)
    assert response.status_code == 201, response.text
    deal = response.json()['id']
    invoice_data = {
        'label': 'First milestone',
        'amount': '123.45',
        'due_date': (
            datetime.now(timezone.utc).date() + timedelta(days=30)
        ).isoformat(),
        'deal_id': deal,
    }
    response = await client.post('/invoices', headers=headers, json=invoice_data)
    assert response.status_code == 201, response.text

    invoice_id = response.json()['id']

    response = await client.post(f'/invoices/{invoice_id}/issue', headers=headers)

    assert response.status_code == 200, response.text
    assert response.json()['status'] == 'issued'

    number = response.json()['number']
    response = await client.get(f'/invoices/{invoice_id}/payment-link', headers=headers)
    assert response.status_code == 200, response.text
    payment_url = response.json()['payment_url']
    token = urlsplit(payment_url).path.rsplit('/', 1)[1]

    async with session_pool() as session:
        invoice = await session.get(Invoice, invoice_id)
        before = (invoice.status, invoice.issue_version, invoice.paid_at)
        saved_token = await session.scalar(
            select(Token).where(Token.invoice_id == invoice_id)
        )
        token_before = (
            saved_token.id,
            saved_token.token_value,
            saved_token.issue_version,
        )

    send_headers = headers
    recipient_id = customer
    send_token = token
    if scenario == 'wrong_token':
        send_token = 'invalid-token'
    if scenario in ('wrong_client', 'foreign_invoice'):
        if scenario == 'foreign_invoice':
            send_headers = other_active_user
        # Свой клиент отправителя: отказ должен произойти именно при проверке
        # принадлежности счёта или его связи с клиентом, а не на первом SELECT.
        response = await client.post(
            '/clients',
            headers=send_headers,
            json={
                'client_name': 'Different recipient',
                'email': 'different@example.com',
            },
        )
        assert response.status_code == 201, response.text
        recipient_id = response.json()['id']
    if scenario == 'anonymous':
        send_headers = {}

    smtp_errors = {
        'smtp_failure': SMTPException,
        'timeout': SMTPTimeoutError,
        'connect_timeout': SMTPConnectTimeoutError,
        'read_timeout': SMTPReadTimeoutError,
    }
    if scenario in smtp_errors:
        # Только вымышленные чувствительные данные: они не должны попасть в HTTP.
        smtp_send.side_effect = [
            smtp_errors[scenario](f'private-smtp-detail fake-password {token}'),
            None,
        ]

    response = await client.post(
        f'/invoices/{invoice_id}/{send_token}/send',
        headers=send_headers,
        params={'client_id': recipient_id},
    )
    assert response.status_code == expected_status, response.text
    if scenario == 'success':
        smtp_send.assert_awaited_once()
        smtp_options = smtp_send.call_args.kwargs
        assert smtp_options['start_tls'] is True
        assert not smtp_options.get('use_tls', False)
        assert smtp_options['hostname'] == settings.EMAIL_HOST
        assert smtp_options['port'] == settings.EMAIL_PORT
        assert smtp_options['timeout'] == 30
        message = smtp_send.call_args.args[0]
        assert message['To'] == 'recipient@example.com'
        assert message['From'] == settings.EMAIL
        assert message['Subject']
        assert message.get_content_type() == 'text/plain'
        body = message.get_content()
        for expected in (
            number,
            'First milestone',
            '123.45 USD',
            invoice_data['due_date'],
            payment_url,
            'Реальные деньги не списываются',
        ):
            assert expected in body
        for placeholder in (
            '{number}',
            '{label}',
            '{amount}',
            '{currency}',
            '{due_date}',
            '{payment_url}',
        ):
            assert placeholder not in body
    elif scenario in smtp_errors:
        smtp_send.assert_awaited_once()
        detail = response.json()['detail']
        if scenario == 'smtp_failure':
            assert detail == 'Ошибка при передаче письма почтовому серверу'
        else:
            assert (
                detail == 'Не удалось подтвердить отправку письма.'
                ' Проверьте почту перед повторной отправкой'
            )
        for secret in ('private-smtp-detail', 'fake-password', token):
            assert secret not in response.text
        # Проверяем состояние уже после сбоя, до ручного повтора.
        async with session_pool() as session:
            invoice = await session.get(Invoice, invoice_id)
            assert (invoice.status, invoice.issue_version, invoice.paid_at) == before
            saved_token = await session.scalar(
                select(Token).where(Token.invoice_id == invoice_id)
            )
            assert (
                saved_token.id,
                saved_token.token_value,
                saved_token.issue_version,
            ) == token_before
        first_message = smtp_send.call_args.args[0]
        repeated = await client.post(
            f'/invoices/{invoice_id}/{token}/send',
            headers=headers,
            params={'client_id': customer},
        )
        assert repeated.status_code == 200, repeated.text
        assert 'Письмо принято почтовым сервером' in repeated.json()['credits']
        assert smtp_send.await_count == 2
        second_message = smtp_send.call_args.args[0]
        assert second_message['To'] == first_message['To']
        assert second_message.get_content() == first_message.get_content()
        assert payment_url in second_message.get_content()
    else:
        smtp_send.assert_not_called()

    # Независимое чтение после запроса: отправка не меняет счёт и токен.
    async with session_pool() as session:
        invoice = await session.get(Invoice, invoice_id)
        assert (invoice.status, invoice.issue_version, invoice.paid_at) == before
        saved_token = await session.scalar(
            select(Token).where(Token.invoice_id == invoice_id)
        )
        assert (
            saved_token.id,
            saved_token.token_value,
            saved_token.issue_version,
        ) == token_before

    if scenario == 'success':
        # Сквозной HTTP-путь по ссылке именно из подготовленного письма.
        emailed_url = next(
            line
            for line in body.splitlines()
            if line.startswith(('http://', 'https://'))
        )
        page_path = urlsplit(emailed_url).path
        assert page_path == f'/pay/{invoice_id}/{token}'
        page = await client.get(page_path)
        assert page.status_code == 200
        assert 'text/html' in page.headers['content-type']
        public_path = f'/invoices/{invoice_id}/{token}'
        public = await client.get(public_path)
        assert public.status_code == 200
        assert public.json()['status'] == 'issued'
        assert public.json()['can_pay'] is True
        paid = await client.post(f'{public_path}/pay')
        assert paid.status_code == 200, paid.text
        assert paid.json()['status'] == 'paid'
        assert paid.json()['paid_at'] is not None
        repeated = await client.post(f'{public_path}/pay')
        assert repeated.status_code == 200
        assert repeated.json() == paid.json()
        refreshed = await client.get(public_path)
        assert refreshed.status_code == 200
        assert refreshed.json() == paid.json()
        assert refreshed.json()['can_pay'] is False
        smtp_send.assert_awaited_once()
