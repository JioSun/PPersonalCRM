from datetime import date
from decimal import Decimal
from typing import Any, Sequence

from sqlalchemy import Row, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from backend.app.crud.invoice import get_invoice_by_engaged_amount
from backend.app.models.database_models import Invoice
from backend.app.models.database_models.client import Client
from backend.app.models.database_models.deal import Deal
from backend.app.schemas.deal import DealUpdate


async def create_deal(
    name: str,
    amount: Decimal | None,
    user_id: str,
    client_id: str,
    deadline: date | None,
    notes: str | None,
    session: AsyncSession,
) -> Deal:
    new_deal = Deal(
        name=name,
        amount=amount,
        user_id=user_id,
        client_id=client_id,
        deadline=deadline,
        notes=notes
    )
    session.add(new_deal)
    await session.commit()
    await session.refresh(new_deal)
    return new_deal


async def get_deals_by_user_id(user_id: str, session: AsyncSession) -> Sequence[Deal]:
    stmt = select(Deal).where(Deal.user_id == user_id)
    result = await session.execute(stmt)
    return result.scalars().all()


async def get_deals_by_client_name(
    client_name: str, session: AsyncSession
) -> Sequence[Deal]:
    stmt = (
        select(Deal)
        .join(Client)
        .options(selectinload(Deal.client))
        .where(Client.client_name == client_name)
    )
    result = await session.execute(stmt)
    return result.scalars().all()


async def get_deals_by_query(
    user_id: str, q: str, offset: int, limit: int, session: AsyncSession
) -> Sequence[Row]:
    stmt = (
        select(
            Deal,
            func.coalesce(
                func.sum(Invoice.amount)
                .filter(Invoice.status == "paid"), 0)
                .label("paid_amount"),
            (Deal.amount - func.coalesce(
                func.sum(Invoice.amount)
                .filter(Invoice.status == "paid"), 0)
            ).label("remaining_to_pay"),
        )
        .outerjoin(Deal.invoices)
        .where(Deal.user_id == user_id)
        .where(Deal.name.ilike(f'%{q}%'))
        .group_by(Deal.id)
        .order_by(Deal.created_at.desc(), Deal.id.desc())
        .limit(limit)
        .offset(offset)
    )
    result = await session.execute(stmt)
    return result.all()


async def get_deal_by_id(
    deal_id: str, user_id: str, session: AsyncSession
) -> Deal | None:
    stmt = select(Deal).where(Deal.id == deal_id, Deal.user_id == user_id)
    result = await session.execute(stmt)
    return result.scalar_one_or_none()


async def get_deal_by_name(name: str, session: AsyncSession) -> Deal | None:
    stmt = select(Deal).where(Deal.name == name)
    result = await session.execute(stmt)
    return result.scalar_one_or_none()


async def update_deal_by_id(
    deal_id: str, user_id: str, deal_in: DealUpdate, session: AsyncSession
) -> Deal | None:
    async with session.begin():
        db_deal = await get_deal_by_id_for_update(deal_id=deal_id, user_id=user_id, session=session)

        if not db_deal:
            return None

        update_data = deal_in.model_dump(exclude_unset=True)
        engage_amount = await get_invoice_by_engaged_amount(deal_id=db_deal.id, user_id=user_id, session=session)

        for key, value in update_data.items():
            setattr(db_deal, key, value)

        if db_deal.amount is not None:
            if db_deal.amount < engage_amount:
                raise ValueError("Сумма счёта не может быть меньше занятой суммы")

        session.add(db_deal)
        await session.flush()
        await session.refresh(db_deal)
        return db_deal


async def get_deals_by_client_id(
    client_id: str, user_id: str, session: AsyncSession
) -> list[Deal]:
    stmt = (
        select(Deal)
        .where(Deal.client_id == client_id, Deal.user_id == user_id)
        .order_by(Deal.created_at)
        .offset(0)
        .limit(10)
    )

    result = await session.execute(stmt)
    return result.scalars().all()


async def get_deal_by_id_for_update(
    deal_id: str,
    user_id: str,
    session: AsyncSession,
) -> Deal | None:
    stmt = (select(Deal)
            .where(Deal.id == deal_id, Deal.user_id == user_id)
            .with_for_update()
            .execution_options(populate_existing=True))
    result = await session.execute(stmt)
    return result.scalar_one_or_none()



