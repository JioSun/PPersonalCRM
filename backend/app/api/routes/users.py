from fastapi import APIRouter, status, Depends, HTTPException
from fastapi.security import OAuth2PasswordRequestForm
from fastapi_cloud_cli.commands.auth import auth_app
from pydantic import EmailStr
from sqlalchemy.orm import Session
from sqlalchemy import select
from backend.app.models.user import UserRead, UserCreate, User
from backend.app.core.db import get_db
from backend.app.core.security import get_password_hash, authenticate_user, create_access_token, create_refresh_token, \
    decode_token
from backend.app.models.secure import Token
from backend.app.api.dependencies import get_current_active_user
import jwt

router = APIRouter(prefix="/auth", tags=["auth"])

@router.post("/register", response_model=UserRead, status_code=status.HTTP_201_CREATED)
async def register_user(user_in: UserCreate, session: Session = Depends(get_db)):
    existing_user = session.execute(select(User).where(User.email == user_in.email)).scalar_one_or_none()

    if existing_user is not None:
        raise HTTPException(status_code=400, detail="Пользователь уже существует")

    user = User(
        username=user_in.username,
        email=user_in.email,
        hashed_password=get_password_hash(user_in.password),
    )

    session.add(user)
    session.commit()
    session.refresh(user)
    return user

@router.post("/refresh", response_model=Token)
async def login(
        form_data: OAuth2PasswordRequestForm = Depends(),
        session: Session = Depends(get_db),
):
    user = await authenticate_user(session, EmailStr(form_data.username), form_data.password)

    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Неверный логин или пароль",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return Token(
        access_token=create_access_token(user.username),
        refresh_token=create_refresh_token(user.username)
    )

@router.post("/me", response_model=Token)
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
    user = session.execute(select(User).where(User.email == email)).scalar_one_or_none()

    if not user:
        raise HTTPException(status_code=401, detail="Пользователь не найден")

    return Token(
        access_token=create_access_token(user.username),
        refresh_token=create_refresh_token(user.username),  # ротация refresh-токена
    )

@router.get("/me", response_model=UserRead)
def read_current_user(current_user: User = Depends(get_current_active_user)):
    return current_user