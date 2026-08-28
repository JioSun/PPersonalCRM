from pydantic_settings import BaseSettings, SettingsConfigDict
from pathlib import Path
from pydantic import (
    PostgresDsn, computed_field, EmailStr
)

BASE_DIR = Path(__file__).resolve().parent.parent.parent.parent
print(BASE_DIR)

class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=BASE_DIR / ".env",
        env_ignore_empty=True,
        extra="ignore"
    )

    #POSTGRES
    POSTGRES_SERVER: str
    POSTGRES_PORT: int = 5432
    POSTGRES_USER: str
    POSTGRES_PASSWORD: str = ""
    POSTGRES_DB: str = ""

    #BACKEND
    SECRET_KEY: str
    ALGORITHM: str
    ACCESS_TOKEN_EXPIRE_MINUTES: int
    REFRESH_TOKEN_EXPIRE_DAYS: int
    SUPER_ADMIN: EmailStr

    #REDIS
    REDIS_HOST: str
    REDIS_PORT: int
    REDIS_DB: str

    #SMTP
    EMAIL: EmailStr
    PASSWORD: str
    EMAIL_HOST: str
    EMAIL_PORT: int

    #GEMINI
    GEMINI_API_KEY: str

    @computed_field
    @property
    def SQLALCHEMY_DATABASE_URI(self) -> PostgresDsn:
        return str(PostgresDsn.build(
            scheme="postgresql+asyncpg",
            username=self.POSTGRES_USER,
            password=self.POSTGRES_PASSWORD,
            host=self.POSTGRES_SERVER,
            port=self.POSTGRES_PORT,
            path=self.POSTGRES_DB,
        ))


settings = Settings()

