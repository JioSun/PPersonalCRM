from datetime import UTC, datetime

from ulid import ULID
import secrets

def generate_ulid():
    return str(ULID())


def generate_invoice_number():
    pass


def get_datetime_utc() -> datetime:
    return datetime.now(UTC)

def generate_token_for_invoice() -> str:
    return secrets.token_urlsafe(16)