from sqlalchemy.orm import Session
from sqlalchemy import select, and_, func

from backend.app.models.client import Client, ClientUpdate
from backend.app.models.deal import Deal
from backend.app.core.db import get_db
import asyncio

async def create_client(
        user_id: str,
        first_name: str,
        last_name: str,
        notes: str,
        username: str,
        session: Session  # <-- Без Depends
) -> Client:
    new_client = Client(
        user_id=user_id,
        first_name=first_name,
        last_name=last_name,
        notes=notes,
        username=username
    )
    session.add(new_client)
    await session.commit()
    await session.refresh(new_client)
    return new_client


async def get_clients_by_user_id(user_id: str, session: Session) -> list[Client]:
    stmt = select(Client).where(Client.user_id == user_id)
    result = await session.execute(stmt)
    return result.scalars().all()


async def existing_client_check(user_id: str, username: str, session: Session) -> Client | None:
    stmt = select(Client).where(and_(Client.username == username, Client.user_id == user_id))
    result = await session.execute(stmt)
    return result.scalar_one_or_none()


async def get_clients_by_query(
        user_id: str,
        q: str,
        offset: int,
        limit: int,
        session: Session
) -> list[Client]:
    stmt = (
        select(Client)
        .where(Client.user_id == user_id)
        .where(Client.username.ilike(f"%{q}%"))
        .limit(limit)
        .offset(offset)
    )
    result = await session.execute(stmt)
    return result.scalars().all()


async def get_client_by_id(client_id: str, session: Session) -> Client | None:
    stmt = select(Client).where(Client.id == client_id)
    result = await session.execute(stmt)
    return result.scalar_one_or_none()


async def update_client_by_id(
        client_id: str,
        client_in: ClientUpdate,
        session: Session
) -> Client | None:
    db_client = await get_client_by_id(client_id=client_id, session=session)
    if not db_client:
        return None

    # Игнорируем поля, которые фронтенд не прислал
    update_data = client_in.model_dump(exclude_unset=True)

    for key, value in update_data.items():
        setattr(db_client, key, value)

    session.add(db_client)
    await session.commit()
    await session.refresh(db_client)

    return db_client

async def get_clients_sum(
        user_id: str,
        session: Session
):
    stmt = (select(Client.id, Client.username, func.sum(Deal.amount))
            .where(Client.user_id == user_id).join(Deal, Deal.client_id == Client.id)
            .group_by(Client.id))

    result = await session.execute(stmt)
    return [dict(row._mapping) for row in result.all()]

async def main():
    async for session in get_db():
        client = await get_clients_sum(
            user_id='01KYT2FHZ4R84JYQ2F36372XF8',
            session=session
        )
        print(client[0])
        break

if '__main__' == __name__:
    asyncio.run(main())