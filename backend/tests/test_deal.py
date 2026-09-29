from decimal import Decimal

import pytest
from pydantic import ValidationError

from ..app.schemas.deal import DealCreate, DealUpdate


def valid_deal_data() -> dict:
    return {
        "name": "Website development",
        "amount": "12.34",
        "deadline": "2026-10-10",
        "client_id": "client-id",
    }


@pytest.mark.parametrize('cls', [DealCreate, DealUpdate])
@pytest.mark.parametrize('name', ["Дизайн", "   Дизайн   "])
async def test_deal_strips_name_whitespace(cls: type[DealCreate] | type[DealUpdate], name: str):
    data = valid_deal_data()
    data["name"] = name

    if cls is DealUpdate:
        data.pop("client_id")

    assert cls(**data).name == "Дизайн"


@pytest.mark.parametrize('cls', [DealCreate, DealUpdate])
async def test_deal_accepts_50_character_name(cls: type[DealCreate] | type[DealUpdate]):
    data = valid_deal_data()
    data["name"] = 'a' * 50

    if cls is DealUpdate:
        data.pop("client_id")

    assert len(cls(**data).name) == 50

@pytest.mark.parametrize('cls', [DealCreate, DealUpdate])
async def test_deal_rejects_name_longer_than_50_characters(cls: type[DealCreate] | type[DealUpdate]):
    data = valid_deal_data()
    data["name"] = 'a' * 51

    if cls is DealUpdate:
        data.pop("client_id")

    with pytest.raises(ValidationError) as exc:
        cls(**data)

    errors = exc.value.errors()
    assert errors[0]["loc"] == ("name",)
    assert errors[0]["type"] == "string_too_long"


async def test_deal_name_is_required_on_create_and_optional_on_update():
    data = valid_deal_data()
    data.pop("name")

    with pytest.raises(ValidationError) as exc:
        DealCreate(**data)

    errors = exc.value.errors()
    assert errors[0]["loc"] == ("name",)
    assert errors[0]["type"] == "missing"

    data.pop("client_id")
    patch = DealUpdate(**data)
    result = patch.model_dump(exclude_unset=True)

    assert "name" not in result


def test_deal_update_includes_only_supplied_fields():
    patch = DealUpdate(name="Дизайн")

    assert patch.model_dump(exclude_unset=True) == {"name": "Дизайн"}

@pytest.mark.parametrize('cls', [DealCreate, DealUpdate])
def test_deal_enforces_notes_length_limit(cls: type[DealCreate] | type[DealUpdate]):
    data = valid_deal_data()
    data['notes'] = 'a' * 5001

    if cls is DealUpdate:
        data.pop("client_id")

    with pytest.raises(ValidationError) as exc:
        cls(**data)

    errors = exc.value.errors()
    assert errors[0]["loc"] == ("notes",)
    assert errors[0]["type"] == "string_too_long"

    data["notes"] = 'a' * 5000
    assert len(cls(**data).notes) == 5000

@pytest.mark.parametrize("field", ["amount", "status", "name"])
def test_deal_update_rejects_explicit_null(field):
    with pytest.raises(ValidationError) as exc:
        DealUpdate(**{field: None})

    assert any(
        error["loc"] == (field,) and error["type"] == "value_error"
        for error in exc.value.errors()
    )

@pytest.mark.parametrize("field", ["deadline", "notes"])
def test_deal_update_preserves_explicit_null_for_clearable_fields(field):
    patch = DealUpdate(**{field: None})

    assert patch.model_dump(exclude_unset=True) == {field: None}

@pytest.mark.parametrize('cls', [DealUpdate, DealCreate])
@pytest.mark.parametrize(
        ("amount", "error_type"),
        [
            ("-1", "greater_than_equal"),
            ("12.342", "decimal_max_places"),
            ("10000000000.00", "decimal_whole_digits"),
        ],
    )
def test_deal_rejects_invalid_amount(amount: str, error_type: str, cls: type[DealCreate] | type[DealUpdate]):
    data = valid_deal_data()
    data["amount"] = amount

    if cls is DealUpdate:
        data.pop("client_id")

    with pytest.raises(ValidationError) as exc:
        cls(**data)

    errors = exc.value.errors()

    assert errors[0]["loc"] == ("amount",)
    assert errors[0]["type"] == error_type

@pytest.mark.parametrize('cls', [DealUpdate, DealCreate])
@pytest.mark.parametrize("amount", ["0", "12", "0.01", "9999999999.99"])
def test_deal_accepts_valid_amount(amount: str, cls: type[DealCreate] | type[DealUpdate]):
    data = valid_deal_data()
    data["amount"] = amount

    if cls is DealUpdate:
        data.pop("client_id")

    assert cls(**data).amount == Decimal(amount)

@pytest.mark.parametrize('cls', [DealUpdate, DealCreate])
@pytest.mark.parametrize(
    ("name", "error_type"),
    [
        ("", ("string_too_short", )),
        (" ", ("string_too_short", )),
        (None, ("string_type", "value_error"))
    ]
)
def test_deal_rejects_invalid_name(cls: type[DealCreate] | type[DealUpdate], name: str | None, error_type: tuple[str, ...]):
    data = valid_deal_data()
    data["name"] = name

    if cls is DealUpdate:
        data.pop("client_id")

    with pytest.raises(ValidationError) as exc:
        cls(**data)

    errors = exc.value.errors()
    assert errors[0]["loc"] == ("name",)
    assert errors[0]["type"] in error_type

def test_deal_update_accepts_empty_patch():
    data = {}

    assert DealUpdate(**data).model_dump(exclude_unset=True) == {}


async def test_deal_clear_notes(client, active_user):
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

    deal_json = {
        "name": "dealA",
        "client_id": response.json().get('id'),
        "deadline": "2021-04-01",
        "notes": 'Test notes'
    }

    deal_response = await client.post('/deals', json=deal_json, headers={'Authorization': active_user['Authorization']})

    assert deal_response.status_code == 201

    before = await client.get(f'/deals/{deal_response.json().get("id")}',
                             headers={'Authorization': active_user['Authorization']})

    assert before.json()["notes"] == "Test notes"

    deal_update_json = {"notes": None}

    deal_update_response = await client.patch(
        f'/deals/{deal_response.json().get("id")}', json=deal_update_json, headers={'Authorization': active_user['Authorization']})

    assert deal_update_response.status_code == 200

    after =  await client.get(f'/deals/{deal_response.json().get("id")}', headers={'Authorization': active_user['Authorization']})

    assert after.status_code == 200
    assert after.json().get("notes") is None
    assert after.json().get("deadline") == deal_json.get("deadline")




