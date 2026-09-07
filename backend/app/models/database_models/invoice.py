from datetime import date, datetime
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import CheckConstraint, ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.app.models.constants import Currency, InvoiceStatus
from backend.app.models.database_models.base import Base, IdMixin, TimestampMixin
from backend.app.models.utils import generate_invoice_number

if TYPE_CHECKING:
    from backend.app.models.database_models.client import Client
    from backend.app.models.database_models.deal import Deal
    from backend.app.models.database_models.user import User

class Invoice(Base, IdMixin, TimestampMixin):
    __tablename__ = "invoices"

    label: Mapped[str] = mapped_column(String(50))
    number: Mapped[str] = mapped_column(default=generate_invoice_number)
    amount: Mapped[Decimal] = mapped_column(default=Decimal('0.00'))
    currency: Mapped[Currency] = mapped_column(default=Currency.USD)
    status: Mapped[InvoiceStatus] = mapped_column(default=InvoiceStatus.DRAFT)
    due_date: Mapped[date] = mapped_column(default=date.today())
    paid_at: Mapped[datetime | None] = mapped_column()
    is_paid: Mapped[bool] = mapped_column(default=False)

    user_id: Mapped[str] = mapped_column(ForeignKey(
        "users.id", ondelete='CASCADE'),
        index=True
    )
    deal_id: Mapped[str | None] = mapped_column(ForeignKey(
        "deals.id", ondelete='CASCADE'), index=True,
        nullable=True
    )
    client_id: Mapped[str] = mapped_column(
        ForeignKey("clients.id", ondelete='CASCADE'),
        index=True
    )

    deal: Mapped["Deal | None"] = relationship(back_populates="invoices", lazy="raise")
    client: Mapped["Client"] = relationship(back_populates="invoices", lazy="raise")
    user: Mapped["User"] = relationship(back_populates="invoices", lazy="raise")

    __table_args__ = (
            UniqueConstraint("user_id", "number"),
            CheckConstraint("amount >= 0", name="ck_invoices_amount_positive")
    )




