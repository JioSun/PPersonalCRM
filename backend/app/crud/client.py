from sqlalchemy.orm import Session
from sqlalchemy import select
from backend.app.models.client import Client

async def create_client(
        session: Session,
        user_id: str,
        first_name: str,
        last_name: str,
        notes: str,
        username: str,
) -> Client:
    new_client = Client(
        user_id=user_id,
        first_name=first_name,
        last_name=last_name,
        notes=notes,
        username=username
    )
    session.add(new_client)
    return new_client

async def get_clients_by_user_id(session: Session, user_id: str) -> list[Client]:
    stmt = select(Client).where(Client.user_id == user_id)
    clients = await session.execute(stmt).scalars().all()

    return clients



