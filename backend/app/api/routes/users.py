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
from backend.app.models.secure import Token
from backend.app.models.user import UserRead, UserCreate, User

router = APIRouter(prefix="/auth", tags=["auth"])

logger = logging.getLogger(__name__)

@router.post("/register", response_model=UserRead, status_code=status.HTTP_201_CREATED)
async def register_user(user_in: UserCreate, session: Session = Depends(get_db)):
    logger.info("Проверка на существование пользователя в бд")
    existing_user = (await session.execute(select(User).where(User.email == user_in.email))).scalar_one_or_none()

    if existing_user is not None:
        logger.error('Пользователь не найден')
        raise HTTPException(status_code=400, detail="Пользователь уже существует")

    user = User(
        username=user_in.username,
        email=user_in.email,
        hashed_password=get_password_hash(user_in.password),
    )

    logger.info("Добавление пользователя в бд")
    session.add(user)
    logger.info('Сохранение пользователя в бд')
    await session.commit()
    await session.refresh(user)
    return user

@router.post("/login", response_model=Token)
async def login(
        form_data: OAuth2PasswordRequestForm = Depends(),
        session: Session = Depends(get_db),
):
    logger.info("Проверка пользователя по паролю и почте")
    user = await authenticate_user(session, form_data.username, form_data.password)

    if not user:
        logger.error('не удалось найти пользователя')
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Неверный логин или пароль",
            headers={"WWW-Authenticate": "Bearer"},
        )
    logger.info('Создание токенов')
    return Token(
        access_token=create_access_token(user.email),
        refresh_token=create_refresh_token(user.email)
    )

@router.post("/refresh", response_model=Token)
async def refresh(refresh_token: str, session: Session = Depends(get_db)):
    try:
        payload = decode_token(refresh_token)
        if payload.get("type") != "refresh":
            raise HTTPException(status_code=401, detail="Неверный тип токена")
        email = payload.get("sub")
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Refresh-токен истёк, требуется повторный вход")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Невалидный токен")
    user = (await session.execute(select(User).where(User.email == email))).scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=401, detail="Пользователь не найден")

    return Token(
        access_token=create_access_token(user.email),
        refresh_token=create_refresh_token(user.email),  # ротация refresh-токена
    )

@router.get("/me", response_model=UserRead)
def read_current_user(current_user: User = Depends(get_current_active_user)):
    return current_user