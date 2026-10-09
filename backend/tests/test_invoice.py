from datetime import date
from decimal import Decimal

import pytest
from pydantic import ValidationError

from ..app.schemas.invoice import InvoiceCreate, InvoiceUpdate


def valid_invoice_data() -> dict:
    return {
        "label": "Website development",
        "amount": "12.34",
        "due_date": "2026-10-10",
        "deal_id": "deal-id",
    }



@pytest.mark.parametrize('cls', [InvoiceCreate, InvoiceUpdate])
@pytest.mark.parametrize('label', ["Дизайн", "   Дизайн   "])
def test_invoice_strips_label_whitespace(cls: type[InvoiceCreate] | type[InvoiceUpdate], label: str):
    data = valid_invoice_data()
    data["label"] = label

    if cls is InvoiceUpdate:
        data.pop("deal_id")

    assert cls(**data).label == "Дизайн"

@pytest.mark.parametrize('cls', [InvoiceCreate, InvoiceUpdate])
def test_invoice_accepts_50_character_label(cls: type[InvoiceCreate] | type[InvoiceUpdate]):
    data = valid_invoice_data()
    data["label"] = 'a' * 50

    if cls is InvoiceUpdate:
        data.pop("deal_id")

    assert len(cls(**data).label) == 50

@pytest.mark.parametrize('cls', [InvoiceCreate, InvoiceUpdate])
def test_invoice_rejects_label_longer_than_50_characters(cls: type[InvoiceCreate] | type[InvoiceUpdate]):
    data = valid_invoice_data()
    data["label"] = 'a' * 51

    if cls is InvoiceUpdate:
        data.pop("deal_id")

    with pytest.raises(ValidationError) as exc:
        cls(**data)

    errors = exc.value.errors()
    assert errors[0]["loc"] == ("label",)
    assert errors[0]["type"] == "string_too_long"

def test_invoice_label_is_required_on_create_and_optional_on_update():
    data = valid_invoice_data()
    data.pop("label")

    with pytest.raises(ValidationError) as exc:
        InvoiceCreate(**data)

    assert exc.value.errors()[0]["loc"] == ("label",)
    assert exc.value.errors()[0]["type"] == "missing"

    data.pop("deal_id")
    patch = InvoiceUpdate(**data)

    assert "label" not in patch.model_dump(exclude_unset=True)


def test_invoice_update_includes_only_supplied_fields():
    patch = InvoiceUpdate(label="Дизайн")

    assert patch.model_dump(exclude_unset=True) == {"label": "Дизайн"}


@pytest.mark.parametrize("field", ["amount", "due_date", "label"])
def test_invoice_update_rejects_explicit_null(field):
    with pytest.raises(ValidationError) as exc:
        InvoiceUpdate(**{field: None})

    assert any(
        error["loc"] == (field,) and error["type"] == "value_error"
        for error in exc.value.errors()
    )


@pytest.mark.parametrize('cls', [InvoiceUpdate, InvoiceCreate])
@pytest.mark.parametrize(
        ("amount", "error_type"),
        [
            ("0", "greater_than"),
            ("-1", "greater_than"),
            ("12.342", "decimal_max_places"),
            ("10000000000.00", "decimal_whole_digits"),
        ],
    )
def test_invoice_rejects_invalid_amount(amount: str, error_type: str, cls: type[InvoiceCreate] | type[InvoiceUpdate]):
    data = valid_invoice_data()
    data["amount"] = amount

    if cls is InvoiceUpdate:
        data.pop("deal_id")

    with pytest.raises(ValidationError) as exc:
        cls(**data)

    errors = exc.value.errors()

    assert errors[0]["loc"] == ("amount",)
    assert errors[0]["type"] == error_type


@pytest.mark.parametrize('cls', [InvoiceUpdate, InvoiceCreate])
@pytest.mark.parametrize("amount", ["12", "0.01", "9999999999.99"])
def test_invoice_accepts_valid_amount(amount: str, cls: type[InvoiceCreate] | type[InvoiceUpdate]):
    data = valid_invoice_data()
    data["amount"] = amount
    if cls is InvoiceUpdate:
        data.pop("deal_id")

    assert cls(**data).amount == Decimal(amount)

@pytest.mark.parametrize('cls', [InvoiceUpdate, InvoiceCreate])
def test_invoice_parses_due_date_as_date(cls: type[InvoiceCreate] | type[InvoiceUpdate]):
    data = valid_invoice_data()
    if cls is InvoiceUpdate:
        data.pop("deal_id")

    model = cls(**data)

    assert isinstance(model.due_date, date)

@pytest.mark.parametrize('cls', [InvoiceUpdate, InvoiceCreate])
@pytest.mark.parametrize(
    ("due_date", "error_type"),
    [
        ("invalid_date", ("date_from_datetime_parsing",)),
        (None, ("date_type", 'value_error'))
    ]
)
def test_invoice_rejects_invalid_due_date(cls: type[InvoiceCreate] | type[InvoiceUpdate], due_date: str | None, error_type: tuple[str, ...]):
    data = valid_invoice_data()
    data["due_date"] = due_date

    if cls is InvoiceUpdate:
        data.pop("deal_id")

    with pytest.raises(ValidationError) as exc:
        cls(**data)

    errors = exc.value.errors()
    assert errors[0]["loc"] == ("due_date",)
    assert errors[0]["type"] in error_type

@pytest.mark.parametrize('cls', [InvoiceUpdate, InvoiceCreate])
@pytest.mark.parametrize(
    ("label", "error_type"),
    [
        ("", ("string_too_short", )),
        (" ", ("string_too_short", )),
        (None, ("string_type", "value_error"))
    ]
)
def test_invoice_rejects_invalid_label(cls: type[InvoiceCreate] | type[InvoiceUpdate], label: str | None, error_type: tuple[str, ...]):
    data = valid_invoice_data()
    data["label"] = label

    if cls is InvoiceUpdate:
        data.pop("deal_id")

    with pytest.raises(ValidationError) as exc:
        cls(**data)

    errors = exc.value.errors()
    assert errors[0]["loc"] == ("label",)
    assert errors[0]["type"] in error_type

def test_invoice_update_accepts_empty_patch():
    data = {}

    assert InvoiceUpdate(**data).model_dump(exclude_unset=True) == {}

async def test_invoice_update_with_only_label(client, active_user):
    client_json = {
        "client_name": "Joe",
        "organization": "JoeCorp",
        "email": "joecorp@example.com",
        "client_status": "lead",
    }

    active_user = active_user[0]

    response = await client.post('/clients', json=client_json,
                                 headers={'Authorization': active_user['Authorization']})

    assert response.status_code == 201

    deal = await client.post('/deals', json={
        'name': 'Test work', 'amount': '1000.00',
        'client_id': response.json()['id'],
    }, headers=active_user)
    assert deal.status_code == 201, deal.text

    invoice_json = {
        "label": "invoiceA",
        "amount": "100",
        "deal_id": deal.json()["id"],
        "due_date": "2021-04-01",
    }

    invoice = await client.post('/invoices', json=invoice_json,
                             headers={'Authorization': active_user['Authorization']})

    assert invoice.status_code == 201

    invoice_id = invoice.json().get('id')
    invoice_update_json = {"label": "Новый этап"}
    invoice_update = await client.patch(f'/invoices/{invoice_id}', json=invoice_update_json, headers={'Authorization': active_user['Authorization']})

    assert invoice_update.status_code == 200

    invoice_get = await client.get(f'/invoices/{invoice_id}', headers={'Authorization': active_user['Authorization']})

    assert invoice_get.status_code == 200
    assert invoice_get.json().get('label') == 'Новый этап'
    assert Decimal(invoice_get.json().get("amount")) == Decimal("100")
    assert invoice_get.json().get("client_id") == invoice.json().get("client_id")
    assert invoice_get.json().get("due_date") == invoice.json().get("due_date")
    assert invoice_get.json().get("status") == invoice.json().get('status')

async def test_invoice_update_with_invalid_amount(client, active_user):
    client_json = {
        "client_name": "Joe",
        "organization": "JoeCorp",
        "email": "joecorp@example.com",
        "client_status": "lead",
    }

    active_user = active_user[0]

    response = await client.post('/clients', json=client_json,
                                 headers={'Authorization': active_user['Authorization']})

    assert response.status_code == 201

    deal = await client.post('/deals', json={
        'name': 'Test work', 'amount': '1000.00',
        'client_id': response.json()['id'],
    }, headers=active_user)
    assert deal.status_code == 201, deal.text

    invoice_json = {
        "label": "Первый этап",
        "amount": "100.00",
        "deal_id": deal.json()["id"],
        "due_date": "2021-04-01",
    }

    invoice = await client.post('/invoices', json=invoice_json,
                             headers={'Authorization': active_user['Authorization']})

    assert invoice.status_code == 201

    invoice_id = invoice.json().get('id')
    invoice_update_json = {"label": "Не должно сохраниться", "amount": "-1"}
    invoice_update = await client.patch(f'/invoices/{invoice_id}', json=invoice_update_json, headers={'Authorization': active_user['Authorization']})

    assert invoice_update.status_code == 422

    invoice_get = await client.get(f'/invoices/{invoice_id}', headers={'Authorization': active_user['Authorization']})

    assert invoice_get.status_code == 200
    assert invoice_get.json().get('client_id') == invoice.json()['client_id']
    assert invoice_get.json().get('due_date') == invoice_json.get('due_date')
    assert invoice_get.json().get('amount') == invoice_json.get('amount')
    assert invoice_get.json().get('label') == invoice_json.get('label')


async def test_invoice_none_amount(client, active_user):
    client_json = {
        "client_name": "Joe",
        "organization": "JoeCorp",
        "email": "joecorp@example.com",
        "client_status": "lead",
    }

    active_user = active_user[0]

    response = await client.post('/clients', json=client_json,
                                 headers={'Authorization': active_user['Authorization']})

    assert response.status_code == 201

    deal = await client.post('/deals', json={
        'name': 'Test work', 'amount': '1000.00',
        'client_id': response.json()['id'],
    }, headers=active_user)
    assert deal.status_code == 201, deal.text

    invoice_json = {
        "label": "Первый этап",
        "amount": "100.00",
        "deal_id": deal.json()["id"],
        "due_date": "2021-04-01",
    }

    invoice = await client.post('/invoices', json=invoice_json,
                                headers={'Authorization': active_user['Authorization']})

    assert invoice.status_code == 201

    invoice_id = invoice.json().get('id')
    invoice_update_json = {"label": "Не должно сохраниться", "amount": None}
    invoice_update = await client.patch(f'/invoices/{invoice_id}', json=invoice_update_json,
                                        headers={'Authorization': active_user['Authorization']})

    assert invoice_update.status_code == 422

    invoice_get = await client.get(f'/invoices/{invoice_id}', headers={'Authorization': active_user['Authorization']})

    assert invoice_get.status_code == 200
    assert invoice_get.json().get('client_id') == invoice.json()['client_id']
    assert invoice_get.json().get('due_date') == invoice_json.get('due_date')
    assert invoice_get.json().get('amount') == invoice_json.get('amount')
    assert invoice_get.json().get('label') == invoice_json.get('label')

@pytest.mark.parametrize('payload', [{}, {'deal_id': None}])
def test_invoice_create_requires_deal(payload):
    data = valid_invoice_data()
    data.pop('deal_id')
    data.update(payload)
    with pytest.raises(ValidationError):
        InvoiceCreate(**data)


def test_invoice_create_rejects_explicit_client():
    data = valid_invoice_data()
    data['client_id'] = 'client-id'
    with pytest.raises(ValidationError):
        InvoiceCreate(**data)
