from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from pydantic import EmailStr
from sqlalchemy.orm import Session
from pwdlib import PasswordHash
from backend.app.models.user import User
from config import settings

import jwt

passwordHash = PasswordHash.recommended()



def get_password_hash(password: str) -> str:
    return passwordHash.hash(password)

def verify_password(password: str, hashed_password: str) -> bool:
    return passwordHash.verify(password, hashed_password)

_DUMMY_HASH = get_password_hash("dummy_password_for_timing_safety")

def create_token(subject: str, expires_delta: timedelta, token_type: str) -> str:
    now = datetime.now(timezone.utc)
    payload = {
        "sub": subject,
        "iat": now,
        "exp": now + expires_delta,
        "type": token_type
    }
    return jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.ALGORITHM)

def create_access_token(username: str) -> str:
    return create_token(username, timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES), "access")

def create_refresh_token(username: str) -> str:
    return create_token(username, timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS), "refresh")

def decode_token(token: str) -> dict:
    return jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])

async def authenticate_user(session: Session, email: EmailStr, password: str) -> User | None:
    stmt = select(User).where(User.email == email)
    user = session.execute(stmt).scalar_one_or_none()


    if not user:
        verify_password(password, _DUMMY_HASH)
        return None

    if not verify_password(password, user.hashed_password):
        return None
    return user
