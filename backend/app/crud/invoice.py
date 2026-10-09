import decimal
from typing import Sequence

from sqlalchemy import Select, and_, func, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload, selectinload

from backend.app.crud.deal import get_deal_by_id_for_update
from backend.app.models.constants import InvoiceStatus
from backend.app.models.dashboard import OverdueInvoice
from backend.app.models.database_models import Client, Deal, Invoice, InvoiceCounter
from backend.app.models.utils import get_datetime_utc
from backend.app.schemas.invoice import InvoiceCreate


async def _next_invoice_number(session: AsyncSession, user_id: str) -> int:
    stmt = (
        pg_insert(InvoiceCounter)
        .values(user_id=user_id, last_number=1)
        .on_conflict_do_update(
            index_elements=[InvoiceCounter.user_id],
            set_={'last_number': InvoiceCounter.last_number + 1},
        )
        .returning(InvoiceCounter.last_number)
    )
    result = await session.execute(stmt)
    return result.scalar_one()

async def create_invoice(
    invoice_in: InvoiceCreate,
    client_id: str,
    status: InvoiceStatus,
    user_id: str,
    session: AsyncSession
) -> Invoice:
    next_number = await _next_invoice_number(session, user_id)
    new_invoice = Invoice(
        label=invoice_in.label,
        due_date=invoice_in.due_date,
        amount=invoice_in.amount,
        status=status,
        user_id=user_id,
        client_id=client_id,
        deal_id=invoice_in.deal_id,
        number=f"INV_{next_number}"
    )
    session.add(new_invoice)
    await session.commit()
    await session.refresh(new_invoice)
    return new_invoice


async def get_invoices_by_user_id(
    session: AsyncSession, user_id: str
) -> Sequence[Invoice]:
    stmt = select(Invoice).where(Invoice.user_id == user_id)
    result = await session.execute(stmt)
    return result.scalars().all()


async def get_invoices_by_client_name(
    client_name: str, session: AsyncSession
) -> Sequence[Invoice]:
    stmt = (
        select(Invoice)
        .join(Client)
        .options(selectinload(Invoice.client))
        .where(Client.client_name == client_name)
    )
    result = await session.execute(stmt)
    return result.scalars().all()


async def existing_invoice_check(
    user_id: str, label: str, session: AsyncSession
) -> Invoice | None:
    stmt = select(Invoice).where(
        and_(Invoice.label == label, Invoice.user_id == user_id)
    )
    result = await session.execute(stmt)
    return result.scalar_one_or_none()


async def get_invoice_by_id(
    invoice_id: str, user_id: str, session: AsyncSession
) -> Invoice | None:
    stmt = select(Invoice).where(Invoice.id == invoice_id, Invoice.user_id == user_id)
    result = await session.execute(stmt)
    return result.scalar_one_or_none()


async def update_invoice_by_id(
    invoice_id: str, user_id: str, valid_data: dict, session: AsyncSession
) -> Invoice | None:
    db_invoice = await get_invoice_by_id(
        invoice_id=invoice_id, user_id=user_id, session=session
    )
    if not db_invoice:
        return None

    for key, value in valid_data.items():
        setattr(db_invoice, key, value)

    session.add(db_invoice)
    await session.commit()
    await session.refresh(db_invoice)
    return db_invoice


async def _get_filtered_invoices_stmt(
    user_id: str,
    q: str | None,
    is_paid: bool | None = None,
    is_back: bool | None = None,
) -> Select:
    stmt = select(Invoice).where(Invoice.user_id == user_id)

    if q:
        stmt = stmt.where(Invoice.label.ilike(f'%{q}%'))

    if is_paid:
        stmt = stmt.where(Invoice.is_paid == is_paid)

    if is_back:
        stmt = stmt.where(Invoice.due_date < get_datetime_utc())

    return stmt


async def get_invoices_list(
    session: AsyncSession,
    user_id: str,
    q: str | None = None,
    offset: int | None = None,
    limit: int | None = None,
    is_paid: bool | None = None,
    is_back: bool | None = None,
) -> list[OverdueInvoice]:
    stmt = await _get_filtered_invoices_stmt(
        user_id=user_id, q=q, is_paid=is_paid, is_back=is_back
    )
    if not limit:
        stmt = stmt
    stmt = stmt.offset(offset).limit(limit)
    result = await session.scalars(stmt)
    return [OverdueInvoice.model_validate(row) for row in result.all()]


async def get_invoices_sum(
    session: AsyncSession,
    user_id: str,
    q: str | None = None,
    is_paid: bool | None = None,
    is_back: bool | None = None,
) -> decimal.Decimal:
    stmt = await _get_filtered_invoices_stmt(
        user_id=user_id, q=q, is_paid=is_paid, is_back=is_back
    )
    stmt = stmt.with_only_columns(func.coalesce(func.sum(Invoice.amount), 0))
    result = await session.scalar(stmt)
    return result


async def get_invoice_with_client(
    invoice_id: str, session: AsyncSession
) -> Invoice | None:
    stmt = (
        select(Invoice)
        .options(joinedload(Invoice.deal).joinedload(Deal.client))
        .where(Invoice.id == invoice_id)
    )
    result = await session.execute(stmt)

    return result.scalar_one_or_none()

async def delete_invoice(
    invoice_id: str,
    user_id: str,
    session: AsyncSession,
) -> bool:
    result = await session.execute(
        select(Invoice).where(
            Invoice.id == invoice_id,
            Invoice.user_id == user_id,
        )
    )
    invoice = result.scalar_one_or_none()

    if invoice is None:
        return False

    await session.delete(invoice)
    await session.commit()
    return True

async def get_invoice_by_id_for_update(
    invoice_id: str,
    user_id: str,
    session: AsyncSession,
) -> Invoice | None:
    stmt = (select(Invoice)
            .where(Invoice.id == invoice_id, Invoice.user_id == user_id)
            .with_for_update()
            .execution_options(populate_existing=True))
    result = await session.execute(stmt)
    return result.scalar_one_or_none()

