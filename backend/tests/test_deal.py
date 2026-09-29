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

async def test_deal_zero_amount():
    data = valid_deal_data()
    data['amount'] = "0"
    with pytest.raises(ValidationError) as exc:
        DealCreate(**data)

    errors = exc.value.errors()
    assert errors[0]["loc"] == ("amount",)
    assert errors[0]['type'] == 'greater_than'

async def test_deal_whole_amount():
    data = valid_deal_data()
    data['amount'] = "12"

    assert DealCreate(**data).amount == Decimal("12")

async def test_deal_with_invalid_amount():
    data = valid_deal_data()
    data['amount'] = "-1"
    with pytest.raises(ValidationError) as exc:
        DealCreate(**data)

    errors = exc.value.errors()
    assert errors[0]["loc"] == ("amount",)
    assert errors[0]['type'] == 'greater_than'

async def test_deal_with_greater_amount_two():
    data = valid_deal_data()
    data['amount'] = "12.345"
    with pytest.raises(ValidationError) as exc:
        DealCreate(**data)

    errors = exc.value.errors()
    assert errors[0]["loc"] == ("amount",)
    assert errors[0]['type'] == 'decimal_max_places'

async def test_deal_normal_name():
    data = valid_deal_data()
    data["name"] = "Дизайн"

    assert DealCreate(**data).name == "Дизайн"

async def test_deal_name_with_space():
    data = valid_deal_data()
    data["name"] = "   Дизайн   "

    assert DealCreate(**data).name == "Дизайн"

async def test_deal_name_with_comma():
    data = valid_deal_data()
    data["name"] = " "

    with pytest.raises(ValidationError) as exc:
        DealCreate(**data)

    errors = exc.value.errors()
    assert errors[0]["loc"] == ("name",)
    assert errors[0]["type"] == "string_too_short"

async def test_deal_name_equals_50():
    data = valid_deal_data()
    data["name"] = 'a' * 50

    assert len(DealCreate(**data).name) == 50

async def test_deal_name_greater_than_50():
    data = valid_deal_data()
    data["name"] = 'a' * 51

    with pytest.raises(ValidationError) as exc:
        DealCreate(**data)

    errors = exc.value.errors()
    assert errors[0]["loc"] == ("name",)
    assert errors[0]["type"] == "string_too_long"

async def test_deal_name_create_and_update():
    data = valid_deal_data()
    data.pop("name")
    data.pop("client_id")

    with pytest.raises(ValidationError) as exc:
        DealCreate(**data)

    errors = exc.value.errors()
    assert errors[0]["loc"] == ("name",)
    assert errors[0]["type"] == "missing"

    patch = DealUpdate(**data)
    result = patch.model_dump(exclude_unset=True)

    assert "name" not in result


def test_patch_allows_missing_fields():
    patch = DealUpdate(name="Дизайн")

    assert patch.model_dump(exclude_unset=True) == {"name": "Дизайн"}


@pytest.mark.parametrize("field", ["amount", "name"])
def test_patch_rejects_explicit_null(field):
    with pytest.raises(ValidationError) as exc:
        DealUpdate(**{field: None})

    assert any(
        error["loc"] == (field,) and error["type"] == "value_error"
        for error in exc.value.errors()
    )
