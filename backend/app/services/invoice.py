from sqlalchemy.ext.asyncio import AsyncSession

from ..crud.deal import get_deal_by_id_for_update
from ..crud.invoice import get_invoice_by_id, get_invoice_by_id_for_update
from ..models.constants import InvoiceStatus
from ..models.database_models import Invoice

def can_issue_invoice(status: InvoiceStatus) -> bool:
    return status == InvoiceStatus.DRAFT

def can_revoke_invoice(status: InvoiceStatus) -> bool:
    return status == InvoiceStatus.ISSUED

def can_cancel_invoice(status: InvoiceStatus) -> bool:
    return status in (InvoiceStatus.ISSUED, InvoiceStatus.DRAFT)

def cancel_invoice(invoice: Invoice) -> None:
    invoice_status = invoice.status
    if not can_cancel_invoice(invoice_status):
        raise ValueError("Объект отменить нельзя")
    invoice.status = InvoiceStatus.CANCELLED

def revoke_invoice(invoice: Invoice) -> None:
    invoice_status = invoice.status
    if not can_revoke_invoice(invoice_status):
        raise ValueError('Объект отозвать нельзя')
    invoice.status = InvoiceStatus.DRAFT

def issue_invoice(invoice: Invoice) -> None:
    invoice_status = invoice.status
    if not can_issue_invoice(invoice_status):
        raise ValueError('Объект нельзя сформировать')
    invoice.issue_version += 1
    invoice.status = InvoiceStatus.ISSUED

async def get_invoice_for_transition(
    invoice_id: str,
    user_id: str,
    session: AsyncSession,
) -> Invoice | None:
    invoice = await get_invoice_by_id(
        invoice_id=invoice_id, user_id=user_id, session=session)
    if invoice is None:
        return None

    deal = await get_deal_by_id_for_update(user_id=user_id, session=session,deal_id=invoice.deal_id)
    if deal is None:
        return None

    invoice = await get_invoice_by_id_for_update(user_id=user_id, invoice_id=invoice_id, session=session)

    return invoice

async def cancel_invoice_in_db(
        invoice_id: str,
        user_id: str,
        session: AsyncSession,
) -> Invoice | None:
    async with session.begin():
        current_invoice = await get_invoice_for_transition(invoice_id=invoice_id, user_id=user_id, session=session)
        if current_invoice is None:
            return None

        cancel_invoice(current_invoice)
        return current_invoice




