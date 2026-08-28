import logging
from fastapi import APIRouter, status, Depends, HTTPException, Query
from sqlalchemy.orm import Session  # или AsyncSession, если используешь asyncpg

from backend.app.api.dependencies import get_current_active_user
from backend.app.core.db import get_db
from backend.app.core.redis_py import get_redis

from backend.app.models.deal import DealRead, DealCreate, DealUpdate
from backend.app.models.user import User

from backend.app.crud.deal import (
    create_deal,
    existing_deal_check,
    get_deals_by_query,
    get_deal_by_id,
    update_deal_by_id
)

router = APIRouter(prefix="/deals", tags=["deal"])
logger = logging.getLogger(__name__)


@router.get("", status_code=status.HTTP_200_OK, response_model=list[DealRead])
async def get_deals(
        q: str = Query(default="", description="Поиск по названию"),
        offset: int = Query(default=0, ge=0),
        limit: int = Query(default=20, le=100),
        current_user: User = Depends(get_current_active_user),
        session: Session = Depends(get_db),
) -> list[DealRead]:
    deals = await get_deals_by_query(
        user_id=current_user.id,
        q=q,
        limit=limit,
        offset=offset,
        session=session  # <-- Передаем сессию явно
    )
    return deals


@router.post("", status_code=status.HTTP_201_CREATED, response_model=DealRead)
async def create_new_deal(
        deal_in: DealCreate,
        client_id: str,
        current_user: User = Depends(get_current_active_user),
        session: Session = Depends(get_db),
        conn = Depends(get_redis)
) -> DealRead:

    deal_existing = await existing_deal_check(
        name=deal_in.name,
        user_id=current_user.id,
        session=session
    )

    if deal_existing:
        logger.error('Сделка уже существует')
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Deal already exists")

    new_deal = await create_deal(
        name=deal_in.name,
        amount=deal_in.amount,
        deadline=deal_in.deadline,
        user_id=current_user.id,
        client_id=client_id,
        session=session
    )
    await conn.delete(f'dashboard:{current_user.id}')
    return new_deal


# ИСПРАВЛЕНО: Добавлен /{deal_id} в путь
@router.get("/{deal_id}", status_code=status.HTTP_200_OK, response_model=DealRead)
async def get_deal(
        deal_id: str,
        session: Session = Depends(get_db),
        current_user: User = Depends(get_current_active_user)
) -> DealRead:
    deal = await get_deal_by_id(deal_id=deal_id, session=session)
    if not deal or deal.user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Deal not found")
    return deal


# ИСПРАВЛЕНО: Добавлен /{deal_id} в путь
@router.patch("/{deal_id}", status_code=status.HTTP_200_OK, response_model=DealRead)
async def update_deal(
        deal_id: str,
        new_deal_data: DealUpdate,
        session: Session = Depends(get_db),
        current_user: User = Depends(get_current_active_user),
        conn = Depends(get_redis)
):
    updated_deal = await update_deal_by_id(
        deal_id=deal_id,
        deal_in=new_deal_data,
        session=session
    )
    if not updated_deal or updated_deal.user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Deal not found")
    await conn.delete(f'dashboard:{current_user.id}')
    return updated_deal