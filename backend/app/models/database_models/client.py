from typing import TYPE_CHECKING, Any

from sqlalchemy import (
    ForeignKey,
    Index,
    String,
    Text,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.app.models.constants import ClientStatus
from backend.app.models.database_models.base import Base, IdMixin, TimestampMixin

if TYPE_CHECKING:
    from backend.app.models.database_models.deal import Deal
    from backend.app.models.database_models.invoice import Invoice
    from backend.app.models.database_models.user import User


class Client(Base, IdMixin, TimestampMixin):
    __tablename__ = 'clients'

    client_name: Mapped[str] = mapped_column(String(50), index=True)
    organization: Mapped[str | None] = mapped_column(String(50), index=True)

    email: Mapped[str | None] = mapped_column(String(100))
    phone: Mapped[str | None] = mapped_column(String(100))
    telegram: Mapped[str | None] = mapped_column(String(100))
    additional_links: Mapped[dict[str, Any] | None] = mapped_column(JSONB)

    client_status: Mapped[ClientStatus] = mapped_column(default=ClientStatus.LEAD)
    notes: Mapped[str | None] = mapped_column(Text)

    timezone: Mapped[str | None] = mapped_column(String(32), default='UTC')

    user_id: Mapped[str] = mapped_column(
        ForeignKey('users.id', ondelete='CASCADE'), index=True
    )

    user: Mapped['User'] = relationship(
        back_populates='clients', passive_deletes=True, lazy='raise'
    )
    deals: Mapped[list['Deal']] = relationship(
        back_populates='client',
        cascade='all, delete-orphan',
        passive_deletes=True,
        lazy='raise',
    )
    invoices: Mapped[list['Invoice']] = relationship(
        back_populates='client', passive_deletes=True, lazy='raise'
    )

    __table_args__ = (Index('ix_name_lower_title', text('lower(client_name)')),)
