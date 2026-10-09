from datetime import date, datetime
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import CheckConstraint, ForeignKey, Index, String, func, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.app.models.constants import DealStatus
from backend.app.models.database_models.base import Base, IdMixin, TimestampMixin

if TYPE_CHECKING:
    from backend.app.models.database_models.client import Client
    from backend.app.models.database_models.invoice import Invoice
    from backend.app.models.database_models.user import User


class Deal(Base, IdMixin, TimestampMixin):
    __tablename__ = 'deals'

    version: Mapped[int] = mapped_column(server_default=text('1'))

    name: Mapped[str] = mapped_column(String(50), index=True, nullable=False,)
    amount: Mapped[Decimal] = mapped_column(nullable=False,)
    currency: Mapped[str] = mapped_column(default="USD", server_default="USD")
    status: Mapped[DealStatus] = mapped_column(default=DealStatus.NEW)
    deadline: Mapped[date | None] = mapped_column(index=True)
    closed_at: Mapped[datetime | None] = mapped_column()
    notes: Mapped[str | None] = mapped_column(String(5000))

    user_id: Mapped[str] = mapped_column(
        ForeignKey('users.id', ondelete='CASCADE'), index=True, nullable=False
    )
    client_id: Mapped[str] = mapped_column(
        ForeignKey('clients.id', ondelete='CASCADE'), index=True, nullable=False
    )

    user: Mapped['User'] = relationship(back_populates='deals', lazy='raise')
    client: Mapped['Client'] = relationship(back_populates='deals', lazy='raise')
    invoices: Mapped[list['Invoice']] = relationship(
        back_populates='deal',
        passive_deletes=True,
        cascade='all, delete-orphan',
        lazy='raise',
    )

    __table_args__ = (
        CheckConstraint('amount >= 0', name='ck_deals_amount_positive'),
        Index('idx_client_id__and__status', 'client_id', 'status'),
        CheckConstraint(currency == "USD", name='ck_deals_currency'),
        CheckConstraint(
            func.length(func.trim(name)) > 0,
            name="ck_deals_name_not_blank",
        )
    )

    __mapper_args__ = {'version_id_col': version}
