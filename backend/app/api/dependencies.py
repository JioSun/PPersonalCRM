from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session
from sqlalchemy import select
from app.core.db import get_db
from app.models.user import User
from app.core.security import decode_token
import jwt

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login") #парсит заголовок и возвращает токен в виде строки

async def get_current_user(
        token: str = Depends(oauth2_scheme),#Парсим токен
        session: Session = Depends(get_db)#Получаем сессию
) -> User:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Не удалось подтвердить учётные данные",
        headers={"WWW-Authenticate": "Bearer"},
    ) #Создание информации при исключении

    try:
        payload = decode_token(token)#декодируем токен
        if payload.get("type") != "access": #Если тип токена не access
            raise credentials_exception #возбуждаем исключение
        email = payload.get("sub")
        if email is None:
            raise credentials_exception
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Токен истёк")
    except jwt.InvalidTokenError:
        raise credentials_exception

    stmt = select(User).where(User.email == email)
    user = session.execute(stmt).scalar_one_or_none()

    if user is None:
        raise credentials_exception
    return user


def get_current_active_user(current_user: User = Depends(get_current_user)) -> User:
    if not current_user.is_active:
        raise HTTPException(status_code=400, detail="Пользователь неактивен")
    return current_user