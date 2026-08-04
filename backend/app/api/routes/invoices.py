import logging
from fastapi import APIRouter, status, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from backend.app.api.dependencies import get_current_active_user
from backend.app.core.db import get_db

from backend.app.models.user import User
from backend.app.models.invoice import InvoiceRead, InvoiceCreate, InvoiceUpdate, InvoiceList

from backend.app.crud.invoice import (
    existing_invoice_check,
    create_invoice,
    get_invoices_list,
    get_invoices_sum,
    get_invoice_by_id,
    update_invoice_by_id
)

router = APIRouter(prefix="/invoices", tags=["invoice"])
logger = logging.getLogger(__name__)


@router.get("", status_code=status.HTTP_200_OK, response_model=InvoiceList, response_model_exclude_none=True)
async def get_invoices(
        q: str = Query(default="", description="Поиск по названию/номеру"),
        is_paid: bool | None = None,
        is_back: bool | None = None,
        total_sum: bool | None = None,
        offset: int = Query(default=0, ge=0, description="Сколько записей пропустить"),
        limit: int = Query(default=20, le=100, description="Сколько записей вернуть"),
        current_user: User = Depends(get_current_active_user),
        session: Session = Depends(get_db)
) -> list[InvoiceRead]:
    if not is_paid:
        is_paid = None
    if not is_back:
        is_back = None
    if not total_sum:
        total_sum = None
    invoices = await get_invoices_list(
        session=session,
        user_id=current_user.id,
        q=q,
        offset=offset,
        limit=limit,
        is_back=is_back,
        is_paid=is_paid,
    )
    if total_sum:
        total_sum = await get_invoices_sum(
            session=session,
            user_id=current_user.id,
            q=q,
            is_back=is_back,
            is_paid=is_paid,
        )
    return {'invoices': invoices, 'total_sum': total_sum}


@router.post("", status_code=status.HTTP_201_CREATED, response_model=InvoiceRead)
async def create_new_invoice(
        invoice_in: InvoiceCreate,
        deal_id: str,
        current_user: User = Depends(get_current_active_user),
        session: Session = Depends(get_db)
) -> InvoiceRead:
    logger.debug("Проверка на существование счета")

    invoice_existing = await existing_invoice_check(
        user_id=current_user.id,
        session=session
    )
    if invoice_existing is not None:
        logger.error('Счет уже существует')
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invoice already exists")

    logger.info('Создание счета')
    new_invoice = await create_invoice(
        is_paid=invoice_in.is_paid if hasattr(invoice_in, 'is_paid') else False,
        user_id=current_user.id,
        deal_id=deal_id,
        mid_amount=invoice_in.mid_amount,
        due_data=invoice_in.due_date,
        session=session
    )
    return new_invoice


@router.get("/{invoice_id}", status_code=status.HTTP_200_OK, response_model=InvoiceRead)
async def get_invoice(
        invoice_id: str,
        session: Session = Depends(get_db),
        current_user: User = Depends(get_current_active_user)
) -> InvoiceRead:
    invoice = await get_invoice_by_id(invoice_id=invoice_id, session=session)
    if not invoice or invoice.user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Invoice not found")
    return invoice


@router.patch("/{invoice_id}", status_code=status.HTTP_200_OK, response_model=InvoiceRead)
async def update_invoice(
        invoice_id: str,
        new_invoice_data: InvoiceUpdate,
        session: Session = Depends(get_db),
        current_user: User = Depends(get_current_active_user)
):
    updated_invoice = await update_invoice_by_id(
        invoice_id=invoice_id,
        invoice_in=new_invoice_data,
        session=session
    )
    if not updated_invoice or updated_invoice.user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Invoice not found")
    return updated_invoice