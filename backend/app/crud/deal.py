import asyncio

from sqlalchemy.orm import Session, selectinload
from sqlalchemy import select, and_
from backend.app.core.db import get_db
from backend.app.models.deal import Deal, DealUpdate
from backend.app.models.client import Client  # Требуется для JOIN'а ниже


async def create_deal(
        name: str,
        amount: str,
        user_id: str,
        client_id: str,
        deadline: str | None,
        session: Session
) -> Deal:
    new_deal = Deal(
        name=name,
        amount=amount,
        user_id=user_id,
        client_id=client_id,
        deadline=deadline,
    )
    session.add(new_deal)
    await session.commit()
    await session.refresh(new_deal)
    return new_deal


async def get_deals_by_user_id(user_id: str, session: Session) -> list[Deal]:
    stmt = select(Deal).where(Deal.user_id == user_id)
    result = await session.execute(stmt)
    return result.scalars().all()


async def get_deals_by_clientname(clientname: str, session: Session) -> list[Deal]:
    # ИСПРАВЛЕНО: Нельзя напрямую фильтровать по Deal.client.username.
    # Если фильтруешь по полю из другой таблицы, нужен JOIN.
    stmt = (
        select(Deal)
        .join(Client)
        .options(selectinload(Deal.client))
        .where(Client.username == clientname)
    )
    result = await session.execute(stmt)
    return result.scalars().all()

async def get_deals_by_query(
        user_id: str,
        q: str,
        offset: int,
        limit: int,
        session: Session
) -> list[Deal]:
    stmt = (
        select(Deal)
        .where(Deal.user_id == user_id)
        .where(Deal.name.ilike(f"%{q}%"))
        .limit(limit)
        .offset(offset)
    )
    result = await session.execute(stmt)
    return result.scalars().all()


async def get_deal_by_id(deal_id: str, user_id: str, session: Session) -> Deal | None:
    stmt = select(Deal).where(Deal.id == deal_id, Deal.user_id == user_id)
    result = await session.execute(stmt)
    return result.scalar_one_or_none()


async def update_deal_by_id(
        deal_id: str,
        user_id: str,
        deal_in: DealUpdate,
        session: Session
) -> Deal | None:
    db_deal = await get_deal_by_id(deal_id=deal_id, user_id=user_id, session=session)
    if not db_deal:
        return None

    update_data = deal_in.model_dump(exclude_unset=True)

    for key, value in update_data.items():
        setattr(db_deal, key, value)

    session.add(db_deal)
    await session.commit()
    await session.refresh(db_deal)

    return db_deal

async def get_deals_by_client_id(client_id: str, session: Session) -> list[dict]:
    stmt = (select(Deal.id, Deal.name, Deal.amount, Deal.deadline)
            .where(Deal.client_id == client_id)
            .order_by(Deal.created_at)
            .offset(0).limit(10))

    result = (await session.execute(stmt)).all()
    return [row._asdict() for row in result]


async def main():
    async for session in get_db():
        res = await get_deals_by_client_id(session=session, client_id='01M0MYJSCZM8S54YDQR0JGX4V6')
        print(res)
        break

if __name__ == '__main__':
    asyncio.run(main())
