from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, func
from backend.app.models.utils import get_datetime_utc
from backend.app.models.invoice import Invoice, InvoiceUpdate
from backend.app.models.client import Client
import decimal

async def create_invoice(
        is_paid: bool,
        label: str,
        deal_id: str,
        user_id: str,
        session: AsyncSession
) -> Invoice:
    new_invoice = Invoice(
        label=label,
        user_id=user_id,
        is_paid=is_paid,
        deal_id=deal_id,
    )
    session.add(new_invoice)
    await session.commit()
    await session.refresh(new_invoice)
    return new_invoice

async def get_invoices_by_user_id(user_id: str, session: AsyncSession) -> list[Invoice]:
    stmt = select(Invoice).where(Invoice.user_id == user_id)
    result = await session.execute(stmt)
    return result.scalars().all()

async def get_invoices_by_clientname(clientname: str, session: AsyncSession) -> list[Invoice]:
    stmt = select(Invoice).join(Client).options(selectinload(Invoice.client)).where(Client.username == clientname)
    result = await session.execute(stmt)
    return result.scalars().all()

async def existing_invoice_check(user_id: str, name: str, session: AsyncSession) -> Invoice | None:
    stmt = select(Invoice).where(and_(Invoice.name == name, Invoice.user_id == user_id))
    result = await session.execute(stmt)
    return result.scalar_one_or_none()


async def get_invoice_by_id(invoice_id: str, session: AsyncSession) -> Invoice | None:
    stmt = select(Invoice).where(Invoice.id == invoice_id)
    result = await session.execute(stmt)
    return result.scalar_one_or_none()

async def update_invoice_by_id(
        invoice_id: str,
        invoice_in: InvoiceUpdate,
        session: AsyncSession
) -> Invoice | None:
    db_invoice = await get_invoice_by_id(invoice_id=invoice_id, session=session)
    if not db_invoice:
        return None

    update_data = invoice_in.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(db_invoice, key, value)

    session.add(db_invoice)
    await session.commit()
    await session.refresh(db_invoice)
    return db_invoice


def _get_filtered_invoices_stmt(
        user_id: str,
        q: str,
        is_paid: bool | None = None,
        is_back: bool | None = None
):
    stmt = select(Invoice).where(Invoice.user_id == user_id)

    if q:
        stmt = stmt.where(Invoice.label.ilike(f"%{q}%"))

    if is_paid is not None:
        stmt = stmt.where(Invoice.is_paid == is_paid)

    if is_back:
        stmt = stmt.where(Invoice.due_date < get_datetime_utc())  # Добавлены ()

    return stmt


async def get_invoices_list(
        session: AsyncSession,
        user_id: str,
        q: str,
        offset: int,
        limit: int,
        is_paid: bool | None = None,
        is_back: bool | None = None,
) -> list[Invoice]:
    stmt = _get_filtered_invoices_stmt(user_id, q, is_paid, is_back)
    stmt = stmt.offset(offset).limit(limit)
    result = await session.scalars(stmt)
    invoices = result.all()
    return invoices if len(invoices) > 0 else None


async def get_invoices_sum(
        session: AsyncSession,
        user_id: str,
        q: str,
        is_paid: bool | None = None,
        is_back: bool | None = None,
) -> decimal.Decimal:
    stmt = _get_filtered_invoices_stmt(user_id, q, is_paid, is_back)
    stmt = stmt.with_only_columns(func.coalesce(func.sum(Invoice.mid_amount), 0))
    result = await session.scalar(stmt)
    return result