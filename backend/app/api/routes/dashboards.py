import logging
import time
from datetime import timedelta

from fastapi import APIRouter, Depends
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.api.dependencies import get_current_active_user
from backend.app.core.db import get_db
from backend.app.core.redis_py import get_redis
from backend.app.crud.client import get_clients_sum
from backend.app.crud.dashboard import (
    get_clients_count_by_user_id,
    get_dashboard_data,
    get_deals_by_status,
    get_overdue_invoices,
)
from backend.app.models.constants import DealStatus
from backend.app.models.dashboard import DashboardResponse
from backend.app.models.database_models import User
from backend.app.models.utils import get_datetime_utc

router = APIRouter(tags=['dashboards'])
logger = logging.getLogger(__name__)


@router.get("/dashboard", response_model=DashboardResponse)
async def dashboard(
    session: AsyncSession =Depends(get_db),
    conn: Redis =Depends(get_redis),
    current_user: User = Depends(get_current_active_user),
):
    start = time.perf_counter()
    current_datetime = get_datetime_utc()
    expiration_date = int((current_datetime.replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(days=1)).timestamp())

    get_result = await conn.get(f"dashboard:{current_user.id}")

    if get_result:
        elapsed = time.perf_counter() - start
        logger.info(f"GET: {get_result}")
        logger.info(f"CACHE HIT: {elapsed * 1000:.2f}ms")
        return DashboardResponse.model_validate_json(get_result)

    overdue_invoices = await get_overdue_invoices(session=session, current_datetime=current_datetime, user_id=current_user.id)
    clients_sum = await get_clients_sum(session=session, user_id=current_user.id)
    dashboard_data = await get_dashboard_data(session=session, current_datetime=current_datetime, user_id=current_user.id)
    deals_by_status = await get_deals_by_status(session=session, user_id=current_user.id)
    clients_count = await get_clients_count_by_user_id(session=session, user_id=current_user.id)


    deals = {row.status: row.deal_count for row in deals_by_status}

    deals.update({status.value: 0 for status in DealStatus if status.value not in deals})

    data = {
        'paid_amount': dashboard_data.paid_amount,
        'unpaid_amount': dashboard_data.unpaid_amount,
        'overdue_amount': dashboard_data.overdue_amount,
        'overdue_count': dashboard_data.overdue_count,
        'clients_summary': clients_sum,
        'overdue_invoice': overdue_invoices,
        'deals_by_status': deals,
        'clients_count': clients_count,
    }
    dashboard_response = DashboardResponse.model_validate(data)

    await conn.set(
        f"dashboard:{current_user.id}",
        dashboard_response.model_dump_json(),
        exat=min(int(current_datetime.timestamp()) + 60, expiration_date)
    )
    elapsed = time.perf_counter() - start
    logger.info(f"CACHE MISS: {elapsed * 1000:.2f}ms")

    return dashboard_response

