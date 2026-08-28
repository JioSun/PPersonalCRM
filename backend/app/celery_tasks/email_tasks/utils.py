from email.mime.multipart import MIMEMultipart

from backend.app.core.db import settings

import smtplib



def smtp_connection(msg: MIMEMultipart):
    with smtplib.SMTP(settings.EMAIL_HOST, settings.EMAIL_PORT) as server:
        server.starttls()
        server.login(settings.EMAIL, settings.PASSWORD)
        server.sendmail(msg['from'], msg['to'], msg.as_string())





