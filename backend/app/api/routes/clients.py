import jwt
from fastapi import APIRouter, status, Depends, HTTPException
from fastapi.security import OAuth2PasswordRequestForm
from pydantic import EmailStr
from sqlalchemy import select
from sqlalchemy.orm import Session
import logging
from backend.app.api.dependencies import get_current_active_user
from backend.app.core.db import get_db
from backend.app.core.security import get_password_hash, authenticate_user, create_access_token, create_refresh_token, \
    decode_token
from backend.app.models.client import ClientRead, ClientCreate, Client
from backend.app.models.secure import Token
from backend.app.models.user import UserRead, UserCreate, User
from backend.app.crud.client import create_client
router = APIRouter(prefix="/client", tags=["clients"])

logger = logging.getLogger(__name__)

@router.post("/create", status_code=status.HTTP_201_CREATED, response_model=ClientRead)
async def create(
        client_in: ClientCreate,
        current_user: User = Depends(get_current_active_user),
        session: Session = Depends(get_db)
) -> ClientRead:
    logger.debug("Проверка на существование клиента")
    stmt = select(Client).where(Client.username == client_in.username)
    result = await session.execute(stmt)
    existing_client = result.scalar_one_or_none()

    if existing_client is not None:
        logger.error('Клиент существует')
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Client already exists")

    logger.info('Создание клиента')
    client = await create_client(
        session=session,
        username=client_in.username,
        first_name=client_in.first_name,
        last_name=client_in.last_name,
        user_id=current_user.id,
        notes=client_in.notes
    )
    logger.info('Сохранение клиента')
    await session.commit()
    await session.refresh(client)

    return client



