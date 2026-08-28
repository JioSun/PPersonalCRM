from fastapi import APIRouter, status
from fastapi.concurrency import run_in_threadpool

from backend.app.celery_tasks.celery_init import app

import logging

router = APIRouter(tags=["job"])
logger = logging.getLogger(__name__)


@router.get('/job/{job_id}', status_code=status.HTTP_200_OK)
async def get_job(job_id: str):
    result = app.AsyncResult(job_id)
    s = await run_in_threadpool(lambda: result.status)

    return {'status': s}