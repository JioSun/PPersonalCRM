from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import (
    CheckConstraint,
    ForeignKey,
    Index,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.app.models.constants import Currency, DealStatus
from backend.app.models.database_models.base import Base, IdMixin, TimestampMixin

if TYPE_CHECKING:
    from backend.app.models.database_models.client import Client
    from backend.app.models.database_models.invoice import Invoice
    from backend.app.models.database_models.user import User



class Deal(Base, IdMixin, TimestampMixin):
    __tablename__ = "deals"
    __mapper_args__ = {"version_id_col": "version"}
    version: Mapped[int] = mapped_column(default=1)

    name: Mapped[str] = mapped_column(index=True)
    amount: Mapped[Decimal] = mapped_column(default=Decimal("0.00"))
    status: Mapped[DealStatus] = mapped_column(default=DealStatus.NEW)
    currency: Mapped[Currency] = mapped_column(default=Currency.USD)
    deadline: Mapped[datetime | None] = mapped_column()
    closed_at: Mapped[datetime | None] = mapped_column()
    notes: Mapped[str | None] = mapped_column(Text)

    user_id: Mapped[str] = mapped_column(
        ForeignKey("users.id", ondelete='CASCADE'),
        index=True
    )
    client_id: Mapped[str] = mapped_column(
        ForeignKey("clients.id", ondelete='CASCADE'),
        index=True
    )

    user: Mapped["User"] = relationship(back_populates="deals", lazy="raise")
    client: Mapped["Client"] = relationship(back_populates="deals", lazy="raise")
    invoices: Mapped[list["Invoice"]] = relationship(
        back_populates="deal",
        passive_deletes=True,
        cascade="all, delete-orphan",
        lazy="raise"
    )

    __table_args__ = (
        CheckConstraint("amount >= 0",  name="ck_deals_amount_positive"),
        Index("idx_client_id__and__status", "client_id", 'status'),
    )




