import logging
from decimal import Decimal
from typing import Sequence

from celery import chain
from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.concurrency import run_in_threadpool
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.api.dependencies import get_current_active_user
from backend.app.celery_tasks.email_tasks.tasks import send_invoice_email
from backend.app.celery_tasks.pdf_tasks.tasks import render_pdf
from backend.app.core.db import get_db
from backend.app.core.redis_py import get_redis
from backend.app.crud.deal import get_deal_by_id
from backend.app.crud.invoice import (
    create_invoice,
    existing_invoice_check,
    get_invoice_by_id,
    get_invoices_list,
    get_invoices_sum,
    update_invoice_by_id, delete_invoice,
)
from backend.app.models.constants import InvoiceStatus
from backend.app.models.database_models import Invoice, User
from backend.app.schemas.invoice import (
    InvoiceCreate,
    InvoiceRead,
    InvoiceUpdate,
)

router = APIRouter(prefix='/invoices', tags=['invoice'])
logger = logging.getLogger(__name__)


@router.get(
    '',
    status_code=status.HTTP_200_OK,
    response_model=None,
    response_model_exclude_none=True,
)
async def get_invoices(
    q: str = Query(default='', description='Поиск по названию/номеру'),
    is_paid: bool | None = None,
    is_back: bool | None = None,
    total_sum: Decimal | None = None,
    offset: int = Query(default=0, ge=0, description='Сколько записей пропустить'),
    limit: int = Query(default=20, le=100, description='Сколько записей вернуть'),
    current_user: User = Depends(get_current_active_user),
    session: AsyncSession = Depends(get_db),
) -> dict[str, Decimal | Sequence[Invoice] | None]:
    summary = None
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
    if total_sum is not None:
        summary = await get_invoices_sum(
            session=session,
            user_id=current_user.id,
            q=q,
            is_back=is_back,
            is_paid=is_paid,
        )

    return {'invoices': invoices, 'total_sum': summary}


@router.post('', status_code=status.HTTP_201_CREATED, response_model=InvoiceRead)
async def create_new_invoice(
    invoice_in: InvoiceCreate,
    current_user: User = Depends(get_current_active_user),
    session: AsyncSession = Depends(get_db),
    conn: Redis = Depends(get_redis),
) -> InvoiceRead:
    logger.debug('Проверка на существование счета')

    invoice_existing = await existing_invoice_check(
        user_id=current_user.id, session=session, label=invoice_in.label
    )

    if invoice_existing is not None:
        logger.error('Счет уже существует')
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail='Invoice already exists'
        )

    deal_existing = await get_deal_by_id(deal_id=invoice_in.deal_id, session=session, user_id=current_user.id)
    if deal_existing is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail='Deal not found'
        )

    new_invoice = await create_invoice(
        invoice_in=invoice_in,
        status=InvoiceStatus.DRAFT,
        client_id=deal_existing.client_id,
        user_id=current_user.id,
        session=session
    )

    await conn.delete(f'dashboard:{current_user.id}')
    return InvoiceRead.model_validate(new_invoice)


@router.get('/{invoice_id}', status_code=status.HTTP_200_OK, response_model=InvoiceRead)
async def get_invoice(
    invoice_id: str,
    session: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> InvoiceRead:
    invoice = await get_invoice_by_id(
        user_id=current_user.id, invoice_id=invoice_id, session=session
    )
    if not invoice or invoice.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail='Invoice not found'
        )
    return InvoiceRead.model_validate(invoice)


@router.patch(
    '/{invoice_id}', status_code=status.HTTP_200_OK, response_model=InvoiceRead
)
async def update_invoice(
    invoice_id: str,
    new_invoice_data: InvoiceUpdate,
    session: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
    conn: Redis = Depends(get_redis),
) -> InvoiceRead:
    invoice_existing = await get_invoice_by_id(invoice_id=invoice_id, session=session, user_id=current_user.id)
    if invoice_existing is not None:
        if invoice_existing.status != InvoiceStatus.DRAFT:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT, detail='Invoice must have status DRAFT'
            )
    else:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Invoice not found')

    update_data = new_invoice_data.model_dump(exclude_unset=True)

    updated_invoice = await update_invoice_by_id(
        invoice_id=invoice_id,
        user_id=current_user.id,
        valid_data=update_data,
        session=session,
    )
    if not updated_invoice:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail='Invoice not found'
        )
    await conn.delete(f'dashboard:{current_user.id}')
    return InvoiceRead.model_validate(updated_invoice)


@router.post('/{invoice_id}/generate_pdf', status_code=status.HTTP_201_CREATED)
async def invoice_pdf(
    invoice_id: str,
    current_user: User = Depends(get_current_active_user),
    session: AsyncSession = Depends(get_db),
    conn: Redis = Depends(get_redis),
) -> dict[str, str]:
    invoice_existing = await get_invoice_by_id(
        invoice_id=invoice_id, user_id=current_user.id, session=session
    )

    if not invoice_existing:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail='Invoice not found'
        )

    result = await run_in_threadpool(
        chain(
            render_pdf.s(invoice_id),
            send_invoice_email.s(current_user.email, invoice_id),
        ).apply_async
    )

    await conn.set(f'job_owner:{result.id}', current_user.id, ex=3600)

    logger.debug(result)
    return {'job_id': result.id}

@router.delete('/{invoice_id}', status_code=status.HTTP_204_NO_CONTENT)
async def delete_invoice_by_id(
        invoice_id: str,
        current_user: User = Depends(get_current_active_user),
        session: AsyncSession = Depends(get_db),
        conn: Redis = Depends(get_redis),
):
    invoice_existing = await get_invoice_by_id(invoice_id=invoice_id, session=session, user_id=current_user.id)
    if not invoice_existing:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Invoice not found')

    if invoice_existing.status != InvoiceStatus.DRAFT:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail='Deletion is supported only when the status is "DRAFT"')

    await delete_invoice(invoice_id=invoice_id, session=session, user_id=current_user.id)
    await conn.delete(f'dashboard:{current_user.id}')