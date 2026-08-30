import logging
from fastapi import APIRouter, status, Depends, HTTPException, Query, Body
from pydantic import Field
from pygments.lexers import q
from sqlalchemy.orm import Session
from sqlalchemy.sql.functions import current_user

from backend.app.api.dependencies import get_current_active_user
from backend.app.core.db import get_db
from backend.app.core.redis_py import get_redis
from backend.app.crud.deal import get_deals_by_client_id, update_deal_by_id, create_deal
from backend.app.models.client import ClientRead, ClientCreate, ClientUpdate
from backend.app.models.deal import DealRead, DealUpdate, DealCreate
from backend.app.models.user import User


from backend.app.crud.client import (
    create_client,
    existing_client_check,
    get_clients_by_query,
    get_client_by_id,
    update_client_by_id
)
from backend.app.working_llm.json_format import note_formatter
from backend.app.working_llm.llm_classes import ExtractedDealInfo

router = APIRouter(prefix="/clients", tags=["clients"])
logger = logging.getLogger(__name__)


@router.post("", status_code=status.HTTP_201_CREATED, response_model=ClientRead)
async def create_new_client(
        client_in: ClientCreate,
        current_user: User = Depends(get_current_active_user),
        session: Session = Depends(get_db),
        conn = Depends(get_redis)
) -> ClientRead:
    logger.debug("Проверка на существование клиента")
    client_existing = await existing_client_check(
        username=client_in.username,
        user_id=current_user.id,
        session=session
    )

    if client_existing:
        logger.error('Клиент существует')
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Client already exists")

    logger.info('Создание клиента')
    client = await create_client(
        username=client_in.username,
        first_name=client_in.first_name,
        last_name=client_in.last_name,
        user_id=current_user.id,
        notes=client_in.notes,
        session=session
    )

    await conn.delete(f'dashboard:{current_user.id}')
    return client


@router.get("", response_model=list[ClientRead], status_code=status.HTTP_200_OK)
async def get_clients(
        q: str = Query(default="", description="Поиск по username"),
        offset: int = Query(default=0, ge=0),
        limit: int = Query(default=20, le=100),
        current_user: User = Depends(get_current_active_user),
        session: Session = Depends(get_db)
) -> list[ClientRead]:

    clients = await get_clients_by_query(
        user_id=current_user.id,
        q=q,
        limit=limit,
        offset=offset,
        session=session
    )
    return clients


@router.get("/{client_id}", response_model=ClientRead, status_code=status.HTTP_200_OK)
async def get_client(
        client_id: str,
        session: Session = Depends(get_db),
        current_user: User = Depends(get_current_active_user)
) -> ClientRead:
    client = await get_client_by_id(client_id=client_id, session=session)
    if not client or client.user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Client not found")
    return client


@router.patch("/{client_id}", response_model=ClientRead, status_code=status.HTTP_200_OK)
async def update_client(
        client_id: str,
        client_in: ClientUpdate,
        session: Session = Depends(get_db),
        current_user: User = Depends(get_current_active_user),
        conn = Depends(get_redis)
):

    updated_client = await update_client_by_id(
        client_id=client_id,
        client_in=client_in,
        user_id=current_user.id,
        session=session
    )

    if not updated_client:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Client not found")
    await conn.delete(f'dashboard:{current_user.id}')
    return updated_client

@router.post('/{client_id}/notes', status_code=status.HTTP_201_CREATED)
async def create_new_client_note(
    client_id: str,
    note: str = Body(max_length=300, min_length=30),
    session: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    deals = await get_deals_by_client_id(
        client_id=client_id, session=session)
    deal_names = ''.join([f"{count}: {deal['name']}\n" for count, deal in enumerate(deals)])
    llm_response = await note_formatter(
        note_text=note,
        deal_names=deal_names)

    if llm_response.matched_index is None and llm_response.name is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail='Переформулируйте свою заметку')

    if llm_response.matched_index is not None:
        filtered_dict = llm_response.model_dump(exclude_none=True)
        filtered_dict.pop('name', None)
        update_deal = await update_deal_by_id(deal_id=deals[llm_response.matched_index]['id'], deal_in=DealUpdate(**filtered_dict), session=session)


        return update_deal

    deal = await create_deal(
        name=llm_response.name,
        amount=llm_response.amount,
        deadline=llm_response.deadline,
        client_id=client_id,
        user_id=current_user.id,
        session=session)


    return deal