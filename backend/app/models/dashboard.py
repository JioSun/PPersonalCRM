import decimal
from datetime import date

from pydantic import BaseModel, ConfigDict, Field

from .constants import DealStatus


class ClientSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    client_id: str = Field(validation_alias='id')
    client_name: str
    total_amount: decimal.Decimal = Field(validation_alias='total_spent')


class OverdueInvoice(BaseModel):
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    invoice_id: str = Field(validation_alias='id')
    deal_id: str
    amount: decimal.Decimal
    due_date: date


class DashboardResponse(BaseModel):
    clients_summary: list[ClientSummary] = Field(default_factory=list)
    overdue_invoice: list[OverdueInvoice] = Field(default_factory=list)
    paid_amount: decimal.Decimal = Field(validation_alias='paid_amount')
    unpaid_amount: decimal.Decimal = Field(validation_alias='unpaid_amount')
    overdue_amount: decimal.Decimal = Field(validation_alias='overdue_amount')
    overdue_count: int = Field(validation_alias='overdue_count')
    deals_by_status: dict[DealStatus, int]
    clients_count: int = 0
