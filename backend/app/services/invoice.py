from datetime import datetime, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from ..crud.deal import get_deal_by_id_for_update
from ..crud.invoice import get_invoice_by_id, get_invoice_by_id_for_update, get_invoice_by_engaged_amount
from ..crud.token import delete_token_by_invoice_id, create_token, get_token_by_invoice_id
from ..models.constants import InvoiceStatus
from ..models.database_models import Invoice, Deal
from ..schemas.invoice import InvoiceUpdate


def can_issue_invoice(status: InvoiceStatus) -> bool:
    return status == InvoiceStatus.DRAFT

def can_revoke_invoice(status: InvoiceStatus) -> bool:
    return status == InvoiceStatus.ISSUED

def can_cancel_invoice(status: InvoiceStatus) -> bool:
    return status in (InvoiceStatus.ISSUED, InvoiceStatus.DRAFT)

def can_pay_invoice(status: InvoiceStatus) -> bool:
    return status == InvoiceStatus.ISSUED

def cancel_invoice(invoice: Invoice) -> None:
    invoice_status = invoice.status
    if not can_cancel_invoice(invoice_status):
        raise ValueError("Объект отменить нельзя")
    invoice.status = InvoiceStatus.CANCELLED

def pay_invoice(
    invoice: Invoice,
    expected_issue_version: int,
    now: datetime,
) -> None:
    invoice_status = invoice.status
    if expected_issue_version != invoice.issue_version:
        raise ValueError('Версии не совпадают')
    if invoice.status is InvoiceStatus.PAID:
        return None
    if not can_pay_invoice(invoice_status):
        raise ValueError("Объект оплатить нельзя")
    if invoice.due_date < now.date():
        raise ValueError('Просроченный счёт')

    invoice.status = InvoiceStatus.PAID
    invoice.paid_at = now
    invoice.is_paid = True
    return None


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
        await delete_token_by_invoice_id(invoice_id=invoice_id, session=session)
        return current_invoice

async def issue_invoice_in_db(
        invoice_id: str,
        user_id: str,
        session: AsyncSession,
) -> Invoice | None:
    async with session.begin():
        current_invoice = await get_invoice_for_transition(invoice_id=invoice_id, user_id=user_id, session=session)
        if current_invoice is None:
            return None

        current_deal: Deal = await get_deal_by_id_for_update(deal_id=current_invoice.deal_id, user_id=user_id, session=session)

        engaged_amount = await get_invoice_by_engaged_amount(deal_id=current_invoice.deal_id, user_id=user_id, session=session)

        if not (current_invoice.amount <= (current_deal.amount - engaged_amount)):
            raise ValueError("Сумма счёта превышает доступную сумму для выставления")

        issue_invoice(current_invoice)
        await create_token(invoice_id=invoice_id, issue_version=current_invoice.issue_version,session=session)
        return current_invoice

async def revoke_invoice_in_db(
        invoice_id: str,
        user_id: str,
        session: AsyncSession,
) -> Invoice | None:
    async with session.begin():
        current_invoice = await get_invoice_for_transition(invoice_id=invoice_id, user_id=user_id, session=session)
        if current_invoice is None:
            return None

        revoke_invoice(current_invoice)
        await delete_token_by_invoice_id(invoice_id=invoice_id, session=session)
        return current_invoice

async def delete_invoice_in_db(
    invoice_id: str,
    user_id: str,
    session: AsyncSession,
) -> bool:
    async with session.begin():
        current_invoice = await get_invoice_for_transition(invoice_id=invoice_id, user_id=user_id, session=session)
        if current_invoice is None:
            return False

        if current_invoice.status is not InvoiceStatus.DRAFT:
            raise ValueError("Статус счёта не предназначен для удаления")

        await session.delete(current_invoice)
        return True

async def patch_invoice_in_db(
    invoice_id: str,
    user_id: str,
    update_body: InvoiceUpdate,
    session: AsyncSession,
) -> Invoice | None:
    async with session.begin():
        current_invoice = await get_invoice_for_transition(invoice_id=invoice_id, user_id=user_id, session=session)
        if current_invoice is None:
            return None

        if current_invoice.status is not InvoiceStatus.DRAFT:
            raise ValueError("Статус счёта не предназначен для обновления")

        for key, value in update_body.model_dump(exclude_unset=True).items():
            setattr(current_invoice, key, value)

        await session.flush()
        await session.refresh(current_invoice)
        return current_invoice

async def pay_invoice_in_db(
        invoice_id: str,
        user_id: str,
        expected_issue_version: int,
        session: AsyncSession,
) -> Invoice | None:
    async with session.begin():
        current_invoice = await get_invoice_for_transition(invoice_id=invoice_id, user_id=user_id, session=session)
        if current_invoice is None:
            return None

        now = datetime.now(timezone.utc)

        pay_invoice(invoice=current_invoice, now=now, expected_issue_version=expected_issue_version)
        return current_invoice

