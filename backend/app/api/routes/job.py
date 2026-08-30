from fastapi import APIRouter, status, Depends, HTTPException
from fastapi.concurrency import run_in_threadpool

from backend.app.api.dependencies import get_current_active_user
from backend.app.celery_tasks.celery_init import app

import logging

from backend.app.core.redis_py import get_redis
from backend.app.models import User

router = APIRouter(prefix="/job", tags=["job"])
logger = logging.getLogger(__name__)


@router.get('/{job_id}', status_code=status.HTTP_200_OK)
async def get_job(job_id: str, current_user: User = Depends(get_current_active_user), conn = Depends(get_redis())):
    truly_user_id = conn.get(f'job_owner:{job_id}')
    if not truly_user_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found")

    if current_user.id != truly_user_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="User not allowed")

    result = app.AsyncResult(job_id)
    s = await run_in_threadpool(lambda: result.status)

    return {'status': s}