import smtplib
from email.mime.multipart import MIMEMultipart

from backend.app.core.config import settings


def smtp_connection(msg: MIMEMultipart) -> None:
    with smtplib.SMTP(settings.EMAIL_HOST, settings.EMAIL_PORT) as server:
        server.starttls()
        server.login(settings.EMAIL, settings.PASSWORD)
        server.sendmail(msg['from'], msg['to'], msg.as_string())
