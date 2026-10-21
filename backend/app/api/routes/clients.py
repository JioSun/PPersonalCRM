import asyncio
import logging
import re

from fastapi import APIRouter, Body, Depends, HTTPException, Query, status
from google.genai.errors import APIError
from pydantic import ValidationError
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.api.dependencies import get_current_active_user
from backend.app.core.config import settings
from backend.app.core.db import get_db
from backend.app.core.redis_py import get_redis
from backend.app.crud.client import (
    create_client,
    get_client_by_client_name,
    get_client_by_id,
    get_clients_by_query,
    update_client_by_id,
)
from backend.app.crud.deal import create_deal, get_deals_by_client_id, update_deal_by_id
from backend.app.middlewares.rate_limiting import check_rate_limit
from backend.app.models.database_models import User
from backend.app.schemas.client import ClientCreate, ClientRead, ClientUpdate
from backend.app.schemas.deal import DealRead, DealUpdate
from backend.app.working_llm.json_format import note_formatter

router = APIRouter(prefix='/clients', tags=['clients'])
logger = logging.getLogger(__name__)


@router.post('', status_code=status.HTTP_201_CREATED, response_model=ClientRead)
async def create_new_client(
    client_in: ClientCreate,
    current_user: User = Depends(get_current_active_user),
    session: AsyncSession = Depends(get_db),
    conn: Redis = Depends(get_redis),
) -> ClientRead:
    logger.debug('Проверка на существование клиента')
    client_existing = await get_client_by_client_name(
        client_name=client_in.client_name, user_id=current_user.id, session=session
    )

    if client_existing:
        logger.error('Клиент существует')
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail='Client already exists'
        )

    logger.info('Создание клиента')
    client = await create_client(
        client_in=client_in,
        user_id=current_user.id,
        session=session,
    )

    await conn.delete(f'dashboard:{current_user.id}')
    return ClientRead.model_validate(client)


@router.get('', response_model=list[ClientRead], status_code=status.HTTP_200_OK)
async def get_clients(
    q: str = Query(default='', description='Поиск по username'),
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=20, le=100),
    current_user: User = Depends(get_current_active_user),
    session: AsyncSession = Depends(get_db),
) -> list[ClientRead]:

    clients = await get_clients_by_query(
        user_id=current_user.id, q=q, limit=limit, offset=offset, session=session
    )
    return [ClientRead.model_validate(obj) for obj in clients]


@router.get('/{client_id}', response_model=ClientRead, status_code=status.HTTP_200_OK)
async def get_client(
    client_id: str,
    session: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> ClientRead:
    client = await get_client_by_id(
        user_id=current_user.id, client_id=client_id, session=session
    )
    if not client or client.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail='Client not found'
        )
    return ClientRead.model_validate(client)


@router.patch('/{client_id}', response_model=None, status_code=status.HTTP_200_OK)
async def update_client(
    client_id: str,
    client_in: ClientUpdate,
    session: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
    conn: Redis = Depends(get_redis),
) -> ClientRead:

    updated_client = await update_client_by_id(
        client_id=client_id,
        client_in=client_in,
        user_id=current_user.id,
        session=session,
    )

    if not updated_client:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail='Client not found'
        )
    await conn.delete(f'dashboard:{current_user.id}')
    return ClientRead.model_validate(updated_client)


@router.post(
    '/{client_id}/notes', status_code=status.HTTP_201_CREATED, response_model=DealRead
)
async def create_new_client_note(
    client_id: str,
    note: str = Body(max_length=300, min_length=30),
    current_user: User = Depends(get_current_active_user),
    conn: Redis = Depends(get_redis),
    session: AsyncSession = Depends(get_db, use_cache=False),
) -> DealRead | None:
    key = f"ratelimit:ai:{current_user.id}"

    async with session.begin():
        current_client = await get_client_by_id(
            user_id=current_user.id, client_id=client_id, session=session)

        if not current_client:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Client not found')

        if not current_client.user_id == current_user.id:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Client not found')

        if len(re.sub(r'\s+', '', note)) == 0:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail='Note are unreache')

        deals = await get_deals_by_client_id(
            client_id=client_id, user_id=current_user.id, session=session
        )
    deal_names = ''.join(
        [f'{count}: {deal.name}\n' for count, deal in enumerate(deals)]
    )

    try:
        try:
            async with asyncio.timeout(settings.GENERAL_TIMEOUT):
                exceeded = await check_rate_limit(conn, key, 5)
                if exceeded:
                    raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail='Превышен лимит AI')
                llm_response = await note_formatter(note_text=note, deal_names=deal_names)
        except TimeoutError:
            raise HTTPException(status_code=status.HTTP_504_GATEWAY_TIMEOUT, detail='Сервис AI не ответил вовремя. Попробуйте позже')
    except ValidationError:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail='Incorrect JSON format of AI response')
    except APIError as e:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail='Сервис AI временно недоступен. Попробуйте позже',
        ) from e

    if not llm_response:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail='Не удалось сформировать заметку')

    matched_index = llm_response.matched_index
    if matched_index is None and llm_response.name is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail='Переформулируйте свою заметку',
        )

    if matched_index is None:
        try:
            deal = await create_deal(
                name=llm_response.name,
                amount=llm_response.amount,
                deadline=llm_response.deadline,
                notes=note,
                client_id=client_id,
                user_id=current_user.id,
                session=session,
            )

            if not deal:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Deal not found')
            await conn.delete(f'dashboard:{current_user.id}')
        except ValueError as e:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT, detail=str(e)
            ) from e
        return DealRead.model_validate(deal)

    if matched_index < 0 or matched_index >= len(deals):
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail='Не удалось сформировать заметку')

    selected_deal = deals[matched_index]

    data = llm_response.model_dump(
        include={'name', 'amount', 'deadline'},
        exclude_none=True,
    )

    if len(data) == 0:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail='Все поля пустые')

    try:
        updated_deal = await update_deal_by_id(
            user_id=current_user.id,
            deal_id=selected_deal.id,
            deal_in=DealUpdate.model_validate(data),
            session=session
        )

        if not updated_deal:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Deal not found')

        await conn.delete(f'dashboard:{current_user.id}')
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail=str(e)
        ) from e
    return DealRead.model_validate(updated_deal)
