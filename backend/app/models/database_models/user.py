from typing import TYPE_CHECKING

from sqlalchemy import Index, String, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.app.models.database_models.base import Base, IdMixin, TimestampMixin

if TYPE_CHECKING:
    from backend.app.models.database_models.client import Client
    from backend.app.models.database_models.deal import Deal
    from backend.app.models.database_models.invoice import Invoice

class User(Base, IdMixin, TimestampMixin):
    __tablename__ = "users"

    email: Mapped[str] = mapped_column()
    is_active: Mapped[bool] = mapped_column(default=True)
    full_name: Mapped[str] = mapped_column()
    username: Mapped[str] = mapped_column()
    hashed_password: Mapped[str] = mapped_column()

    timezone: Mapped[str] = mapped_column(String(32), default="UTC")

    clients: Mapped[list["Client"]] = relationship(
        back_populates="user",
        cascade="all, delete-orphan",
        lazy="raise",
        passive_deletes=True
    )
    deals: Mapped[list["Deal"]] = relationship(
        back_populates="user",
        cascade="all, delete-orphan",
        lazy="raise",
        passive_deletes=True
    )
    invoices: Mapped[list["Invoice"]] = relationship(
        back_populates="user",
        cascade="all, delete-orphan",
        lazy="raise",
        passive_deletes=True
    )

    __table_args__ = (
        Index("ix_users_email_lower", text("lower(email)"), unique=True),
        Index("ix_username_lower", text("lower(username)"), unique=True)
    )

