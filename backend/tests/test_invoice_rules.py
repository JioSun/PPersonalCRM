from decimal import Decimal

from ..app.models.constants import InvoiceStatus
from ..app.services.invoice import can_issue_invoice, can_revoke_invoice, can_cancel_invoice, cancel_invoice, revoke_invoice, issue_invoice
from ..app.models.database_models.invoice import Invoice
import pytest

def test_status_draft_for_editing():
    assert can_issue_invoice(InvoiceStatus.DRAFT) == True

@pytest.mark.parametrize('status', [InvoiceStatus.PAID, InvoiceStatus.ISSUED, InvoiceStatus.CANCELLED])
def test_unsupported_status_for_editing(status: InvoiceStatus):
    assert can_issue_invoice(status) == False

def test_status_issued_for_revoke():
    assert can_revoke_invoice(InvoiceStatus.ISSUED) == True

@pytest.mark.parametrize('status', [InvoiceStatus.PAID, InvoiceStatus.DRAFT, InvoiceStatus.CANCELLED])
def test_unsupported_status_for_revoke(status: InvoiceStatus):
    assert can_revoke_invoice(status) == False

def test_allowed_statuses_for_cancel():
    assert can_cancel_invoice(InvoiceStatus.ISSUED) == True
    assert can_cancel_invoice(InvoiceStatus.DRAFT) == True

@pytest.mark.parametrize('status', [InvoiceStatus.PAID, InvoiceStatus.CANCELLED])
def test_unsupported_status_for_cancel(status: InvoiceStatus):
    assert can_cancel_invoice(status) == False

@pytest.mark.parametrize('status', [InvoiceStatus.ISSUED, InvoiceStatus.DRAFT])
def test_allowed_status_change(status: InvoiceStatus):
    invoice = Invoice(label='dummy', amount=Decimal("100"), due_date="2026-10-08", status=status)

    cancel_invoice(invoice)
    assert invoice.status == InvoiceStatus.CANCELLED

@pytest.mark.parametrize('status', [InvoiceStatus.PAID, InvoiceStatus.CANCELLED])
def test_cancel_invoice_rejects_unsupported_status(status: InvoiceStatus):
    invoice = Invoice(label='dummy', amount=Decimal("100"), due_date="2026-10-08", status=status)
    with pytest.raises(ValueError):
        cancel_invoice(invoice)

    assert invoice.status == status

def test_can_revoke():
    invoice = Invoice(label='dummy', amount=Decimal("100"), due_date="2026-10-08", status=InvoiceStatus.ISSUED)
    revoke_invoice(invoice)
    assert invoice.status == InvoiceStatus.DRAFT

@pytest.mark.parametrize('status', [InvoiceStatus.DRAFT, InvoiceStatus.PAID, InvoiceStatus.CANCELLED])
def test_reject_revoke(status: InvoiceStatus):
    invoice = Invoice(label='dummy', amount=Decimal("100"), due_date="2026-10-08", status=status)
    with pytest.raises(ValueError):
        revoke_invoice(invoice)

    assert invoice.status == status

def test_can_issued():
    invoice = Invoice(label='dummy', amount=Decimal("100"), due_date="2026-10-08", status=InvoiceStatus.DRAFT, issue_version=0)
    issue_invoice(invoice)
    assert invoice.status == InvoiceStatus.ISSUED

@pytest.mark.parametrize('status', [InvoiceStatus.ISSUED, InvoiceStatus.PAID, InvoiceStatus.CANCELLED])
def test_reject_issue(status: InvoiceStatus):
    invoice = Invoice(label='dummy', amount=Decimal("100"), due_date="2026-10-08", status=status, issue_version=3)
    with pytest.raises(ValueError):
        issue_invoice(invoice)

    assert invoice.status == status
    assert invoice.issue_version == 3


def test_issue_version_updated():
    invoice = Invoice(
        label='dummy',
        amount=Decimal("100"),
        due_date="2026-10-08",
        status=InvoiceStatus.DRAFT,
        issue_version=0)

    issue_invoice(invoice)
    assert invoice.issue_version == 1
    assert invoice.status == InvoiceStatus.ISSUED

    revoke_invoice(invoice)
    assert invoice.issue_version == 1
    assert invoice.status == InvoiceStatus.DRAFT

    issue_invoice(invoice)
    assert invoice.issue_version == 2
    assert invoice.status == InvoiceStatus.ISSUED