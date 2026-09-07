from datetime import UTC, datetime

from ulid import ULID


def generate_ulid():
    return str(ULID())

def generate_invoice_number():
    pass


def get_datetime_utc() -> datetime:
    return datetime.now(UTC)
