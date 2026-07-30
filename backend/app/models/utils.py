from ulid import ULID
from datetime import datetime, UTC

def generate_ulid():
    return str(ULID())

def get_datetime_utc() -> datetime:
    return datetime.now(UTC)