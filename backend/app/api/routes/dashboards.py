import logging
import time

from fastapi import APIRouter, Depends, Query

from backend.app.api.dependencies import get_current_active_user
from backend.app.core.db import get_db
from backend.app.core.redis_py import get_redis
from backend.app.crud.client import get_clients_sum
from backend.app.crud.invoice import get_invoices_list, get_invoices_by_user_id
from backend.app.models.dashboard import DashboardResponce
from backend.app.models.user import User

router = APIRouter(tags=["dashboards"])
logger = logging.getLogger(__name__)

@router.get("/dashboard", response_model=DashboardResponce)
async def dashboard(
        session = Depends(get_db),
        conn = Depends(get_redis),
        current_user: User = Depends(get_current_active_user)):
    start = time.perf_counter()
    get_result = await conn.get(f"dashboard:{current_user.id}")

    if get_result:
        elapsed = time.perf_counter() - start
        logger.info(f'GET: {get_result}')
        logger.info(f"CACHE HIT: {elapsed * 1000:.2f}ms")
        return DashboardResponce.model_validate_json(get_result)

    clients_sum = await get_clients_sum(session=session, user_id=current_user.id)
    overdue = await get_invoices_by_user_id(session=session, user_id=current_user.id)

    data = DashboardResponce(
        clients_summary=clients_sum,
        overdue_invoice=overdue
    )

    await conn.set(f"dashboard:{current_user.id}", data.model_dump_json(), ex=60)
    elapsed = time.perf_counter() - start
    logger.info(f"CACHE HIT: {elapsed * 1000:.2f}ms")
    return data