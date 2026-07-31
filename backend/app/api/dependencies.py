import logging

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session
from sqlalchemy import select
from backend.app.core.db import get_db
from backend.app.models.user import User
from backend.app.core.security import decode_token
import jwt

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login") #парсит заголовок и возвращает токен в виде строки

logger = logging.getLogger(__name__)

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
        payload = decode_token(token)
        logger.info("Декодирование токена")
        if payload.get("type") != "access":
            logger.error("Несовпадение типа токена")#Если тип токена не access
            raise credentials_exception #возбуждаем исключение
        email = payload.get("sub")
        logger.info("Парсинг эл.почты из payload")
        if email is None:
            logger.info("Не удалось найти почту")
            raise credentials_exception
    except jwt.ExpiredSignatureError:
        logger.info("Токен истёк")
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Токен истёк")
    except jwt.InvalidTokenError:
        logger.info("Неизвестная ошибка токена")
        raise credentials_exception

    stmt = select(User).where(User.email == email)
    result = await session.execute(stmt)
    logger.info('Выполен запрос на поиск юзера по почте')
    user = result.scalar_one_or_none()

    if user is None:
        logger.error('Юзер не найден')
        raise credentials_exception
    logger.info("Успешный возвращение найденного пользователя")
    return user


def get_current_active_user(current_user: User = Depends(get_current_user)) -> User:
    if not current_user.is_active:
        raise HTTPException(status_code=400, detail="Пользователь неактивен")
    return current_user