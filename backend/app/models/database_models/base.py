import re
from datetime import datetime
from decimal import Decimal

from sqlalchemy import BigInteger, DateTime, Enum, Numeric, String, func
from sqlalchemy.orm import (
    DeclarativeBase,
    Mapped,
    declared_attr,
    mapped_column,
)

from backend.app.models.constants import ClientStatus, DealStatus, InvoiceStatus
from backend.app.models.utils import generate_ulid


class Base(DeclarativeBase):
    type_annotation_map = {
        int: BigInteger,
        str: String(255),
        Decimal: Numeric(12, 2),
        datetime: DateTime(timezone=True),
        ClientStatus: Enum(
            ClientStatus,
            name='client_status',
            values_callable=lambda x: [e.value for e in x],
        ),
        InvoiceStatus: Enum(
            InvoiceStatus,
            name='invoice_status',
            values_callable=lambda x: [e.value for e in x],
        ),
        DealStatus: Enum(
            DealStatus,
            name='deal_status',
            values_callable=lambda x: [e.value for e in x],
        ),
    }

    @declared_attr.directive
    def __tablename__(cls) -> str:
        name = re.sub(r'(?<!^)(?=[A-Z])', '_', cls.__name__).lower()
        return f'{name}s' if not name.endswith('s') else name


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(
        server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        server_default=func.now(), onupdate=func.now(), nullable=False
    )


class IdMixin:
    id: Mapped[str] = mapped_column(String(26), default=generate_ulid, primary_key=True)
