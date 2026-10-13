import logging

from fastapi import APIRouter, Depends, HTTPException, Query, status
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.api.dependencies import get_current_active_user
from backend.app.core.db import get_db
from backend.app.core.redis_py import get_redis
from backend.app.crud.client import get_client_by_id
from backend.app.crud.deal import (
    create_deal,
    get_deal_by_id,
    get_deals_by_query,
    update_deal_by_id,
)
from backend.app.crud.invoice import get_invoice_by_engaged_amount, get_invoice_by_paid_status
from backend.app.models.database_models import User
from backend.app.schemas.deal import DealCreate, DealRead, DealUpdate, DealDetailRead, DealListRead

router = APIRouter(prefix='/deals', tags=['deal'])
logger = logging.getLogger(__name__)


@router.get('', status_code=status.HTTP_200_OK, response_model=list[DealListRead])
async def get_deals(
    q: str = Query(default='', description='Поиск по названию'),
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=20, le=100),
    current_user: User = Depends(get_current_active_user),
    session: AsyncSession = Depends(get_db),
) -> list[DealListRead]:
    deals = await get_deals_by_query(
        user_id=current_user.id,
        q=q,
        limit=limit,
        offset=offset,
        session=session,
    )

    list_of_deals = []

    for row in deals:
        current_deal = DealRead.model_validate(row.Deal).model_dump()
        current_deal.update({"remaining_to_pay": row.remaining_to_pay, "paid_amount": row.paid_amount})
        list_of_deals.append(current_deal)

    return [DealListRead.model_validate(deal) for deal in list_of_deals]


@router.post('', status_code=status.HTTP_201_CREATED, response_model=DealRead)
async def create_new_deal(
    deal_in: DealCreate,
    current_user: User = Depends(get_current_active_user),
    session: AsyncSession = Depends(get_db),
    conn: Redis = Depends(get_redis),
) -> DealRead:

    client_existing = await get_client_by_id(
        client_id=deal_in.client_id, user_id=current_user.id, session=session
    )
    if not client_existing:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail='Client not found'
        )

    new_deal = await create_deal(
        name=deal_in.name,
        amount=deal_in.amount,
        deadline=deal_in.deadline,
        user_id=current_user.id,
        notes=deal_in.notes,
        client_id=deal_in.client_id,
        session=session,
    )
    await conn.delete(f'dashboard:{current_user.id}')
    return DealRead.model_validate(new_deal)


@router.get('/{deal_id}', status_code=status.HTTP_200_OK, response_model=DealDetailRead)
async def get_deal(
    deal_id: str,
    session: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> DealRead:
    deal = await get_deal_by_id(
        deal_id=deal_id, user_id=current_user.id, session=session
    )
    if not deal:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail='Deal not found'
        )

    available_to_issue = await get_invoice_by_engaged_amount(deal_id=deal_id, session=session, user_id=current_user.id)
    remaining_to_pay = await get_invoice_by_paid_status(deal_id=deal_id, session=session, user_id=current_user.id)

    for name, amount in (('available_to_issue', available_to_issue), ('remaining_to_pay', remaining_to_pay)):
        setattr(deal, name, deal.amount - amount)

    return DealDetailRead.model_validate(deal)


@router.patch('/{deal_id}', status_code=status.HTTP_200_OK, response_model=DealRead)
async def update_deal(
    deal_id: str,
    new_deal_data: DealUpdate,
    current_user: User = Depends(get_current_active_user),
    session: AsyncSession = Depends(get_db, use_cache=False),
    conn: Redis = Depends(get_redis),
) -> DealRead:
    try:
        updated_deal = await update_deal_by_id(
            deal_id=deal_id, user_id=current_user.id, deal_in=new_deal_data, session=session
        )
        if not updated_deal:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail='Deal not found'
            )
        await conn.delete(f'dashboard:{current_user.id}')
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail=str(e)
        ) from e
    return DealRead.model_validate(updated_deal)

