"""Validated request and response models for the HomePilot API."""

from datetime import datetime
from enum import StrEnum
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class TaskSessionMode(StrEnum):
    STATIONARY_VOICE = "stationary_voice"
    MOBILE_CAPTURE = "mobile_capture"


class TaskSessionState(StrEnum):
    COLLECTING = "collecting"
    AWAITING_CONFIRMATION = "awaiting_confirmation"
    STOPPING = "stopping"
    EXECUTING = "executing"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    EXPIRED = "expired"


class TaskSessionCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    mode: TaskSessionMode


class TaskSession(BaseModel):
    model_config = ConfigDict(extra="forbid")

    session_id: UUID
    mode: TaskSessionMode
    state: TaskSessionState
    revision: int = Field(ge=0)
    expires_at: datetime
