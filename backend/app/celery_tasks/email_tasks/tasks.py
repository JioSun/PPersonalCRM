import base64
import logging
import smtplib
from email.mime.application import MIMEApplication
from email.mime.multipart import MIMEMultipart

from backend.app.celery_tasks.celery_init import app
from backend.app.celery_tasks.email_tasks.utils import smtp_connection
from backend.app.core.config import settings

logger = logging.getLogger(__name__)

@app.task(
    bind=True,
    name='send_invoice_email',
    max_retries=5,
    retry_backoff=True,
    acks_late=True,
)
def send_invoice_email(self, base64_pdf: str, email: str, invoice_id: str):
    msg = MIMEMultipart()
    msg["From"] = settings.EMAIL
    msg["To"] = email
    msg['Subject'] = f"Invoice ID: {invoice_id}"
    filename = f'{invoice_id}.pdf'
    attachment = MIMEApplication(base64.b64decode(base64_pdf), Name=filename)
    attachment.add_header('Content-Disposition', 'attachment', filename=filename)
    msg.attach(attachment)

    try:
        smtp_connection(msg)
    except smtplib.SMTPAuthenticationError:
        logger.error("Неверные учётные данные — retry не поможет")
        raise
    except (smtplib.SMTPException, ConnectionError) as exc:
        logger.warning(f"Временная ошибка, повтор: {exc}")
        raise self.retry(exc=exc)
    except Exception as e:
        logger.error(f'Произошла критическая ошибка: {e}')
        raise self.retry(exc=e)


