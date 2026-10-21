import logging
from pathlib import Path
from typing import Any

from fastapi import APIRouter, status
from fastapi.responses import FileResponse
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from ....app.core.config import Settings


router = APIRouter(prefix='/pay', tags=['pay'])
logger = logging.getLogger(__name__)
settings = Settings()
PAGE_PATH = Path(__file__).resolve().parent / "templates" / "button.html"


@router.get('/{invoice_id}/{token}', status_code=status.HTTP_200_OK, response_class=HTMLResponse)
async def get_pay_page(
        invoice_id: str,
        token: str,
) -> Any:
    return FileResponse(PAGE_PATH, media_type="text/html")

