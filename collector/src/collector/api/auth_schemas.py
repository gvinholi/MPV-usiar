"""HTTP contracts for internal authentication."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, StrictStr


class InternalLoginRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    email: StrictStr = Field(min_length=3, max_length=320)
    password: StrictStr = Field(min_length=15, max_length=128)


class InternalSessionResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    token_type: str
    session_token: str
    csrf_token: str
    idle_expires_at: datetime
    absolute_expires_at: datetime
