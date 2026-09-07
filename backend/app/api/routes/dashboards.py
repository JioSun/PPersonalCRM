import logging

from fastapi import APIRouter

router = APIRouter(tags=["dashboards"])
logger = logging.getLogger(__name__)

'''
@router.get("/dashboard", response_model=DashboardResponce)
async def dashboard(
    session: AsyncSession =Depends(get_db),
    conn: Redis =Depends(get_redis),
    current_user: User = Depends(get_current_active_user),
):
    start = time.perf_counter()
    get_result = await conn.get(f"dashboard:{current_user.id}")

    if get_result:
        elapsed = time.perf_counter() - start
        logger.info(f"GET: {get_result}")
        logger.info(f"CACHE HIT: {elapsed * 1000:.2f}ms")
        return DashboardResponce.model_validate_json(get_result)

    clients_sum = await get_clients_sum(session=session, user_id=current_user.id)
    overdue = await get_invoices_list(
        user_id=current_user.id,
        is_back=True,
        session=session
    )

    data = DashboardResponce(clients_summary=clients_sum, overdue_invoice=overdue)

    await conn.set(f"dashboard:{current_user.id}", data.model_dump_json(), ex=60)
    elapsed = time.perf_counter() - start
    logger.info(f"CACHE HIT: {elapsed * 1000:.2f}ms")
    return data
'''