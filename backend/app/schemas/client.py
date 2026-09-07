import re
from datetime import datetime
from zoneinfo import available_timezones

import phonenumbers
from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

from backend.app.models.constants import ClientStatus


class ClientValidators:
    @field_validator("phone")
    @classmethod
    def validate_phone_number(cls, v: str | None) -> str | None:
        if v is None:
            return v
        try:
            parsed = phonenumbers.parse(v, None)
        except phonenumbers.NumberParseException:
            raise ValueError("Invalid phone number")
        if not phonenumbers.is_valid_number(parsed):
            raise ValueError("Invalid phone number")
        return v

    @field_validator("telegram")
    @classmethod
    def validate_telegram(cls, v: str | None) -> str | None:
        if v is None:
            return v
        v = v.lstrip("@")
        if not re.match(r"^[a-zA-Z0-9_]{5,32}$", v):
            raise ValueError("Invalid Telegram username")
        return v

    @field_validator("timezone")
    @classmethod
    def validate_timezone(cls, v: str | None) -> str | None:
        if v is None:
            return v
        if v not in available_timezones():
            raise ValueError(f"Unknown timezone: {v}")
        return v

    @field_validator("email", mode="before")
    @classmethod
    def validate_email(cls, v: str | None) -> str | None:
        return v.strip().lower() if v is not None else v

class ClientFields(BaseModel):
    client_name: str = Field(min_length=3, max_length=50)
    organization: str | None = Field(default=None, max_length=50)
    email: EmailStr | None = None
    phone: str | None = None
    telegram: str | None = None
    additional_links: dict[str, str] | None = None
    client_status: ClientStatus = ClientStatus.LEAD
    notes: str | None = Field(default=None, max_length=5000)
    timezone: str | None = None

class ClientBase(ClientValidators, ClientFields):
    pass

class ClientCreate(ClientBase):
    pass


class ClientUpdate(ClientValidators, BaseModel):
    client_name: str | None = None
    organization: str | None = None
    phone: str | None = None
    email: EmailStr | None = None
    telegram: str | None = None
    client_status: ClientStatus | None = None
    notes: str | None = None
    timezone: str | None = None



class ClientRead(ClientFields):
    model_config = ConfigDict(from_attributes=True)

    id: str
    created_at: datetime
    updated_at: datetime
