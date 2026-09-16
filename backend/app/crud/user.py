from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.core.security import get_password_hash
from backend.app.models.database_models import User
from backend.app.schemas.user import UserCreate


async def create_user(user_in: UserCreate, session: AsyncSession) -> User:
    user = User(
        username=user_in.username,
        email=user_in.email,
        full_name=user_in.full_name,
        hashed_password=get_password_hash(user_in.password),
    )

    session.add(user)
    await session.commit()
    await session.refresh(user)
    return user
