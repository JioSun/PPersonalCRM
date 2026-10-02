from datetime import date, datetime
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import CheckConstraint, ForeignKey, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.app.models.constants import InvoiceStatus
from backend.app.models.database_models.base import Base, IdMixin, TimestampMixin
from backend.app.models.utils import generate_invoice_number

if TYPE_CHECKING:
    from backend.app.models.database_models.client import Client
    from backend.app.models.database_models.deal import Deal
    from backend.app.models.database_models.user import User


class Invoice(Base, IdMixin, TimestampMixin):
    __tablename__ = 'invoices'

    label: Mapped[str] = mapped_column(String(50), nullable=False)
    number: Mapped[str] = mapped_column(default=generate_invoice_number)
    amount: Mapped[Decimal] = mapped_column(nullable=False)
    currency: Mapped[str] = mapped_column(default="USD", server_default="USD",)
    status: Mapped[InvoiceStatus] = mapped_column(default=InvoiceStatus.DRAFT)
    due_date: Mapped[date] = mapped_column(nullable=False)
    paid_at: Mapped[datetime | None] = mapped_column(default=None)
    is_paid: Mapped[bool] = mapped_column(default=False)

    user_id: Mapped[str] = mapped_column(
        ForeignKey('users.id', ondelete='CASCADE'), index=True, nullable=False
    )
    deal_id: Mapped[str] = mapped_column(
        ForeignKey('deals.id', ondelete='CASCADE'), index=True, nullable=False
    )
    client_id: Mapped[str] = mapped_column(
        ForeignKey('clients.id', ondelete='CASCADE'), index=True, nullable=False
    )

    deal: Mapped['Deal'] = relationship(back_populates='invoices', lazy='raise')
    client: Mapped['Client'] = relationship(back_populates='invoices', lazy='raise')
    user: Mapped['User'] = relationship(back_populates='invoices', lazy='raise')

    __table_args__ = (
        UniqueConstraint('user_id', 'number'),
        CheckConstraint('amount > 0', name='ck_invoices_amount_positive'),
        CheckConstraint(currency == "USD", name='ck_invoices_currency'),
        CheckConstraint(func.length(func.trim(label)) > 0, name="ck_invoices_label_not_blank")
    )

class InvoiceCounter(Base):
    __tablename__ = 'invoice_counters'

    user_id: Mapped[str] = mapped_column(
        ForeignKey('users.id', ondelete='CASCADE'), primary_key=True
    )
    last_number: Mapped[int] = mapped_column(default=0)
