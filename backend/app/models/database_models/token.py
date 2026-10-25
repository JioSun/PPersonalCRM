from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..utils import generate_token_for_invoice
from .base import Base, IdMixin, TimestampMixin

if TYPE_CHECKING:
    from ....app.models.database_models.invoice import Invoice


class Token(Base, IdMixin, TimestampMixin):
    __tablename__ = 'tokens'

    token_value: Mapped[str] = mapped_column(
        default=generate_token_for_invoice, unique=True
    )
    issue_version: Mapped[int] = mapped_column(nullable=False)

    invoice_id: Mapped[str] = mapped_column(
        ForeignKey('invoices.id', ondelete='CASCADE'),
        index=True,
        nullable=False,
        unique=True,
    )

    invoice: Mapped['Invoice'] = relationship(back_populates='tokens', lazy='raise')
