from typing import Any

from mypy.nodes import Sequence
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.models.dashboard import ClientSummary
from backend.app.models.database_models.client import Client
from backend.app.models.database_models.deal import Deal
from backend.app.schemas.client import ClientUpdate


async def create_client(
    user_id: str,
    notes: str | None,
    client_name: str,
    session: AsyncSession,
) -> Client:
    new_client = Client(
        user_id=user_id,
        notes=notes,
        client_name=client_name,
    )
    session.add(new_client)
    await session.commit()
    await session.refresh(new_client)
    return new_client


async def get_clients_by_user_id(
    user_id: str, session: AsyncSession
) -> Sequence[Client]:
    stmt = select(Client).where(Client.user_id == user_id)
    result = await session.execute(stmt)
    return result.scalars().all()


async def get_clients_by_query(
    user_id: str, q: str, offset: int, limit: int, session: AsyncSession
) -> Sequence[Client]:
    stmt = (
        select(Client)
        .where(Client.user_id == user_id)
        .where(Client.client_name.ilike(f'%{q}%'))
        .limit(limit)
        .offset(offset)
    )
    result = await session.execute(stmt)
    return result.scalars().all()


async def get_client_by_id(
    client_id: str, user_id: str, session: AsyncSession
) -> Client | None:
    stmt = select(Client).where(Client.id == client_id, Client.user_id == user_id)
    result = await session.execute(stmt)
    return result.scalar_one_or_none()


async def get_client_by_client_name(
    client_name: str, user_id: str, session: AsyncSession
) -> Client | None:
    stmt = select(Client).where(
        Client.client_name == client_name, Client.user_id == user_id
    )
    result = await session.execute(stmt)
    return result.scalar_one_or_none()


async def update_client_by_id(
    client_id: str, user_id: str, client_in: ClientUpdate, session: AsyncSession
) -> Client | None:
    db_client = await get_client_by_id(
        client_id=client_id, user_id=user_id, session=session
    )
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


async def get_clients_sum(user_id: str, session: AsyncSession) -> list[ClientSummary]:
    stmt = (
        select(
            Client.id, Client.client_name, func.sum(Deal.amount).label('total_spent')
        )
        .where(Client.user_id == user_id)
        .join(Deal, Deal.client_id == Client.id)
        .group_by(Client.id)
    )

    result = await session.execute(stmt)
    return [ClientSummary.model_validate(row) for row in result.all()]
