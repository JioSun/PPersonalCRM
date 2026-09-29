from decimal import Decimal

import pytest
from pydantic import ValidationError
from ..app.schemas.invoice import InvoiceCreate, InvoiceUpdate


def valid_invoice_data() -> dict:
    return {
        "label": "Website development",
        "amount": "12.34",
        "due_date": "2026-10-10",
        "client_id": "client-id",
    }

async def test_invoice_zero_amount():
    data = valid_invoice_data()
    data['amount'] = "0"
    with pytest.raises(ValidationError) as exc:
        InvoiceCreate(**data)

    errors = exc.value.errors()
    assert errors[0]["loc"] == ("amount",)
    assert errors[0]['type'] == 'greater_than'

async def test_invoice_whole_amount():
    data = valid_invoice_data()
    data['amount'] = "12"

    assert InvoiceCreate(**data).amount == Decimal("12")

async def test_invoice_with_invalid_amount():
    data = valid_invoice_data()
    data['amount'] = "-1"
    with pytest.raises(ValidationError) as exc:
        InvoiceCreate(**data)

    errors = exc.value.errors()
    assert errors[0]["loc"] == ("amount",)
    assert errors[0]['type'] == 'greater_than'

async def test_invoice_with_greater_amount_two():
    data = valid_invoice_data()
    data['amount'] = "12.345"
    with pytest.raises(ValidationError) as exc:
        InvoiceCreate(**data)

    errors = exc.value.errors()
    assert errors[0]["loc"] == ("amount",)
    assert errors[0]['type'] == 'decimal_max_places'

async def test_invoice_normal_label():
    data = valid_invoice_data()
    data["label"] = "Дизайн"

    assert InvoiceCreate(**data).label == "Дизайн"

async def test_invoice_label_with_space():
    data = valid_invoice_data()
    data["label"] = "   Дизайн   "

    assert InvoiceCreate(**data).label == "Дизайн"

async def test_invoice_label_with_comma():
    data = valid_invoice_data()
    data["label"] = " "

    with pytest.raises(ValidationError) as exc:
        InvoiceCreate(**data)

    errors = exc.value.errors()
    assert errors[0]["loc"] == ("label",)
    assert errors[0]["type"] == "string_too_short"

async def test_invoice_label_equals_50():
    data = valid_invoice_data()
    data["label"] = 'a' * 50

    assert len(InvoiceCreate(**data).label) == 50

async def test_invoice_label_greater_than_50():
    data = valid_invoice_data()
    data["label"] = 'a' * 51

    with pytest.raises(ValidationError) as exc:
        InvoiceCreate(**data)

    errors = exc.value.errors()
    assert errors[0]["loc"] == ("label",)
    assert errors[0]["type"] == "string_too_long"

async def test_invoice_label_create_and_update():
    data = valid_invoice_data()
    data.pop("label")
    data.pop("client_id")

    with pytest.raises(ValidationError) as exc:
        InvoiceCreate(**data)

    errors = exc.value.errors()
    assert errors[0]["loc"] == ("label",)
    assert errors[0]["type"] == "missing"

    patch = InvoiceUpdate(**data)
    result = patch.model_dump(exclude_unset=True)

    assert "label" not in result


def test_patch_allows_missing_fields():
    patch = InvoiceUpdate(label="Дизайн")

    assert patch.model_dump(exclude_unset=True) == {"label": "Дизайн"}


@pytest.mark.parametrize("field", ["amount", "due_date", "label"])
def test_patch_rejects_explicit_null(field):
    with pytest.raises(ValidationError) as exc:
        InvoiceUpdate(**{field: None})

    assert any(
        error["loc"] == (field,) and error["type"] == "value_error"
        for error in exc.value.errors()
    )
