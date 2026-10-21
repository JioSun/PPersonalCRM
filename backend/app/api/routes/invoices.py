import logging
from decimal import Decimal
from email.message import EmailMessage
from pathlib import Path
from aiosmtplib import SMTPException, SMTPTimeoutError
from typing import Sequence, Any

import aiosmtplib
from fastapi import APIRouter, Depends, HTTPException, Query, status
from redis.asyncio import Redis
from redis.exceptions import RedisError
from sqlalchemy.ext.asyncio import AsyncSession

from ...crud.client import get_client_by_id
from ...models.utils import get_datetime_utc
from ...schemas.invoice import InvoiceSecretRead
from ...services.invoice import can_pay_invoice, pay_invoice_in_db
from ....app.api.dependencies import get_current_active_user
from ....app.core.config import Settings
from ....app.core.db import get_db
from ....app.core.redis_py import get_redis
from ....app.crud.deal import get_deal_by_id
from ....app.crud.invoice import (
    create_invoice,
    existing_invoice_check,
    get_invoice_by_id,
    get_invoices_list,
    get_invoices_sum,
)
from ....app.crud.token import get_token_by_invoice_id
from ....app.models.constants import InvoiceStatus
from ....app.models.database_models import Invoice, User
from ....app.schemas.invoice import (
    InvoiceCreate,
    InvoiceRead,
    InvoiceUpdate,
)
from ....app.services.invoice import (
    cancel_invoice_in_db,
    delete_invoice_in_db,
    issue_invoice_in_db,
    patch_invoice_in_db,
    revoke_invoice_in_db,
)

router = APIRouter(prefix='/invoices', tags=['invoice'])
logger = logging.getLogger(__name__)
settings = Settings()

@router.get(
    '',
    status_code=status.HTTP_200_OK,
    response_model=None,
    response_model_exclude_none=True,
)
async def get_invoices(
    q: str = Query(default='', description='Поиск по названию/номеру'),
    is_paid: bool = False,
    is_back: bool = False,
    total_sum: bool = False,
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
    session: AsyncSession = Depends(get_db, use_cache=False),
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
    current_user: User = Depends(get_current_active_user),
    session: AsyncSession = Depends(get_db, use_cache=False),
) -> InvoiceRead:
    invoice = await get_invoice_by_id(
        user_id=current_user.id, invoice_id=invoice_id, session=session
    )
    if not invoice or invoice.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail='Invoice not found'
        )
    return InvoiceRead.model_validate(invoice)

@router.get('/{invoice_id}/payment-link', status_code=status.HTTP_200_OK)
async def get_invoice_payment_link(
    invoice_id: str,
    current_user: User = Depends(get_current_active_user),
    session: AsyncSession = Depends(get_db, use_cache=False),
) -> dict[str, str]:
    invoice = await get_invoice_by_id(
        user_id=current_user.id, invoice_id=invoice_id, session=session
    )
    get_token = await get_token_by_invoice_id(invoice_id=invoice_id, session=session)

    if not invoice or invoice.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail='Invoice not found'
        )

    if not get_token:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail='Links are not match')

    link = f"{settings.MAIN_URL.rstrip('/')}/pay/{invoice_id}/{get_token.token_value}"

    return {"payment_url": link}


@router.patch(
    '/{invoice_id}', status_code=status.HTTP_200_OK, response_model=InvoiceRead
)
async def update_invoice(
    invoice_id: str,
    new_invoice_data: InvoiceUpdate,
    current_user: User = Depends(get_current_active_user),
    session: AsyncSession = Depends(get_db, use_cache=False),
    conn: Redis = Depends(get_redis),
) -> InvoiceRead:
    try:
        current_invoice = await patch_invoice_in_db(
            invoice_id=invoice_id,
            session=session,
            user_id=current_user.id,
            update_body=new_invoice_data
        )

        if not current_invoice:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail='Invoice not found'
            )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))
    await conn.delete(f'dashboard:{current_user.id}')
    return InvoiceRead.model_validate(current_invoice)


@router.delete('/{invoice_id}', status_code=status.HTTP_204_NO_CONTENT)
async def delete_invoice_by_id(
        invoice_id: str,
        current_user: User = Depends(get_current_active_user),
        session: AsyncSession = Depends(get_db, use_cache=False),
        conn: Redis = Depends(get_redis),
):
    try:
        current_invoice = await delete_invoice_in_db(invoice_id=invoice_id, session=session, user_id=current_user.id)
        if not current_invoice:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Invoice not found')
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))
    await conn.delete(f'dashboard:{current_user.id}')

@router.post('/{invoice_id}/cancel', status_code=status.HTTP_200_OK, response_model=InvoiceRead)
async def cancel_invoice(
        invoice_id: str,
        current_user: User = Depends(get_current_active_user),
        session: AsyncSession = Depends(get_db, use_cache=False),
        conn: Redis = Depends(get_redis),
):
    try:
        invoice = await cancel_invoice_in_db(invoice_id=invoice_id, session=session, user_id=current_user.id)

    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e)) from e

    if not invoice:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Invoice not found')
    await conn.delete(f'dashboard:{current_user.id}')
    await session.refresh(invoice)
    return InvoiceRead.model_validate(invoice)

@router.post('/{invoice_id}/revoke', status_code=status.HTTP_200_OK, response_model=InvoiceRead)
async def revoke_invoice(
        invoice_id: str,
        current_user: User = Depends(get_current_active_user),
        session: AsyncSession = Depends(get_db, use_cache=False),
        conn: Redis = Depends(get_redis),
):
    try:
        invoice = await revoke_invoice_in_db(invoice_id=invoice_id, session=session, user_id=current_user.id)

    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e)) from e

    if not invoice:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Invoice not found')
    await conn.delete(f'dashboard:{current_user.id}')
    await session.refresh(invoice)
    return InvoiceRead.model_validate(invoice)

@router.post('/{invoice_id}/issue', status_code=status.HTTP_200_OK, response_model=InvoiceRead)
async def issue_invoice(
        invoice_id: str,
        current_user: User = Depends(get_current_active_user),
        session: AsyncSession = Depends(get_db, use_cache=False),
        conn: Redis = Depends(get_redis),
):
    try:
        invoice = await issue_invoice_in_db(invoice_id=invoice_id, session=session, user_id=current_user.id)

    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e)) from e

    if not invoice:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Invoice not found')
    await conn.delete(f'dashboard:{current_user.id}')
    await session.refresh(invoice)
    return InvoiceRead.model_validate(invoice)

@router.get('/{invoice_id}/{token}', response_model=InvoiceSecretRead)
async def get_invoice_by_token(
        invoice_id: str,
        token: str,
        session: AsyncSession = Depends(get_db, use_cache=False),
) -> InvoiceSecretRead:
    async with session.begin():
        current_token = await get_token_by_invoice_id(invoice_id=invoice_id, session=session)

        if not current_token:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Invoice not found')

        if not current_token.token_value == token:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Invoice not found')

        current_invoice = await session.get(Invoice, invoice_id)

        if not current_invoice:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Invoice not found')

        if  current_invoice.status not in (InvoiceStatus.PAID, InvoiceStatus.ISSUED):
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Invoice not found')

        if not current_invoice.issue_version == current_token.issue_version:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Invoice not found')

    current_date = get_datetime_utc().date()
    is_overdue = current_invoice.status is InvoiceStatus.ISSUED and current_date > current_invoice.due_date

    data = {
        "number": current_invoice.number,
        "label": current_invoice.label,
        "amount": current_invoice.amount,
        "currency": current_invoice.currency,
        "due_date": current_invoice.due_date,
        "status": current_invoice.status,
        "paid_at": current_invoice.paid_at,
        "is_overdue": is_overdue,
        "can_pay": can_pay_invoice(current_invoice.status) and not is_overdue
    }

    return InvoiceSecretRead.model_validate(data)

@router.post('/{invoice_id}/{token}/pay', status_code=status.HTTP_200_OK, response_model=InvoiceSecretRead)
async def pay_invoice(
        invoice_id: str,
        token: str,
        session: AsyncSession = Depends(get_db, use_cache=False),
        conn: Redis = Depends(get_redis),
) -> InvoiceSecretRead:
        async with session.begin():
            current_token = await get_token_by_invoice_id(invoice_id=invoice_id, session=session)

            if not current_token:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Invoice not found')

            if not current_token.token_value == token:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Invoice not found')

            current_invoice = await session.get(Invoice, invoice_id)

            if not current_invoice:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Invoice not found')

            if current_invoice.status not in (InvoiceStatus.PAID, InvoiceStatus.ISSUED):
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Invoice not found')

            if not current_invoice.issue_version == current_token.issue_version:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Invoice not found')

            current_date = get_datetime_utc().date()
            is_overdue = current_invoice.status is InvoiceStatus.ISSUED and current_date > current_invoice.due_date

            if is_overdue:
                raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail='Invoice is overdue')

        try:
            invoice = await pay_invoice_in_db(
                invoice_id=invoice_id,
                expected_issue_version=current_token.issue_version,
                user_id=current_invoice.user_id,
                session=session
            )

        except ValueError as e:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e)) from e

        if not invoice:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Invoice not found')

        data = {
            "number": invoice.number,
            "label": invoice.label,
            "amount": invoice.amount,
            "currency": invoice.currency,
            "due_date": invoice.due_date,
            "status": invoice.status,
            "paid_at": invoice.paid_at,
            "is_overdue": is_overdue,
            "can_pay": can_pay_invoice(invoice.status) and not is_overdue
        }
        try:
            await conn.delete(f'dashboard:{invoice.user_id}')
        except RedisError:
            logger.exception("Ошибка очистки invoice_id%s", invoice_id)
        return InvoiceSecretRead.model_validate(data)

@router.post('/{invoice_id}/{token}/send', status_code=status.HTTP_200_OK)
async def send_email(
        invoice_id: str,
        token: str,
        client_id: str,
        current_user: User = Depends(get_current_active_user),
        session: AsyncSession = Depends(get_db, use_cache=False),
) -> Any:
    async with session.begin():
        current_client = await get_client_by_id(client_id=client_id, user_id=current_user.id, session=session)

        if current_client is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Email not send')


        current_token = await get_token_by_invoice_id(invoice_id=invoice_id, session=session)

        if not current_token:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Email not send')

        if not current_token.token_value == token:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail='Token are not match')

        if not invoice_id == current_token.invoice_id:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail='Invoice id are not match')


        current_invoice = await get_invoice_by_id(invoice_id=invoice_id, user_id=current_user.id, session=session)

        if not current_invoice:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Email not send')

        if not current_client.id == current_invoice.client_id:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Email not send')
    payment_url = f"{settings.MAIN_URL.rstrip('/')}/pay/{invoice_id}/{current_token.token_value}"
    msg = EmailMessage()

    msg['Subject'] = "PersonalCRM: вам пришёл счёт"
    msg['From'] = settings.EMAIL
    if current_client.email is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Email not sent')

    msg['To'] = current_client.email

    with open(Path(__file__).resolve().parent / "templates" / "template_text.txt", 'r', encoding='utf-8') as f:
        template_text = f.read().format(
            label=current_invoice.label,
            amount=f"{current_invoice.amount:.2f}",
            currency=current_invoice.currency,
            number=current_invoice.number,
            due_date=current_invoice.due_date.isoformat(),
            payment_url=payment_url,
        )
    msg.set_content(template_text)

    try:
        await aiosmtplib.send(
            msg,
            hostname=settings.EMAIL_HOST,
            port=settings.EMAIL_PORT,
            password=settings.PASSWORD,
            timeout=30,
            username=settings.EMAIL,
            start_tls=True
        )

        return {'credits': f'Письмо принято почтовым сервером: {current_client.email}'}
    except SMTPTimeoutError:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail='Не удалось подтвердить отправку письма. Проверьте почту перед повторной отправкой')
    except SMTPException as e:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail='Ошибка при передаче письма почтовому серверу')
