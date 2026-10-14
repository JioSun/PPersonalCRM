from datetime import datetime

from sqlalchemy import select, func, Row
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.models.database_models import Invoice, Client, Deal


async def get_dashboard_data(user_id: str, current_datetime: datetime, session: AsyncSession) -> Row:
    stmt = select(
        func.coalesce(func.sum(Invoice.amount).filter(Invoice.status == "paid"), 0).label("paid_amount"),
        func.coalesce(func.sum(Invoice.amount).filter(Invoice.status == "issued"), 0).label("unpaid_amount"),
        func.coalesce(func.sum(Invoice.amount).filter(Invoice.status == "issued", Invoice.due_date < current_datetime.date()), 0).label("overdue_amount"),
        func.count(Invoice.id).filter(Invoice.status == "issued",Invoice.due_date < current_datetime.date()).label("overdue_count"),
    ).select_from(Invoice).where(Invoice.user_id == user_id)

    results = (await session.execute(stmt))
    return results.one()

async def get_overdue_invoices(user_id: str, current_datetime: datetime, session: AsyncSession) -> list[Invoice]:
    stmt = (select(Invoice)
            .where(
        Invoice.user_id == user_id,
        Invoice.status == "issued",
        Invoice.due_date < current_datetime.date()
    ))

    results = await session.execute(stmt)
    return results.scalars().all()

async def get_clients_count_by_user_id(user_id: str, session: AsyncSession) -> int:
    stmt = select(func.count(Client.id).label("clients_count")).where(Client.user_id == user_id)

    results = await session.execute(stmt)

    return results.one().clients_count

async def get_deals_by_status(user_id: str, session: AsyncSession) -> list[Row]:
    stmt = select(Deal.status, func.count(Deal.id).label("deal_count")).where(Deal.user_id == user_id).group_by(Deal.status)

    results = await session.execute(stmt)

    return results.all()


