from datetime import datetime, timedelta, timezone
from unittest.mock import patch

import pytest

from backend.app.models.constants import InvoiceStatus
from backend.app.schemas.invoice import InvoiceRead


@pytest.mark.parametrize('status', list(InvoiceStatus))
@pytest.mark.parametrize('offset', [-1, 0, 1])
def test_overdue_utc_date_and_json(status, offset):
    now = datetime(2030, 6, 15, 0, 1, tzinfo=timezone.utc)
    invoice = InvoiceRead(
        id='i', client_id='c', deal_id='d', number='INV_1',
        status=status, label='Test', currency='USD', amount='1.00',
        paid_at=None, created_at=now, updated_at=now,
        due_date=now.date() + timedelta(days=offset),
    )
    with patch('backend.app.schemas.invoice.datetime') as clock:
        clock.now.return_value = now
        expected = status == InvoiceStatus.ISSUED and offset == -1
        assert invoice.is_overdue is expected
        assert invoice.model_dump(mode='json')['is_overdue'] is expected
        clock.now.assert_called_with(timezone.utc)


def test_overdue_recomputed_after_utc_midnight():
    now = datetime(2030, 6, 15, 23, 59, tzinfo=timezone.utc)
    invoice = InvoiceRead(
        id='i', client_id='c', deal_id='d', number='INV_1',
        status=InvoiceStatus.ISSUED, label='Test', currency='USD', amount='1.00',
        paid_at=None, created_at=now, updated_at=now, due_date=now.date(),
    )
    with patch('backend.app.schemas.invoice.datetime') as clock:
        clock.now.return_value = now
        assert invoice.is_overdue is False
        clock.now.return_value = now + timedelta(minutes=1)
        assert invoice.is_overdue is True
        assert invoice.status == InvoiceStatus.ISSUED
