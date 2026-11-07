"""Pydantic schemas for AuditEvent and ClaimStatusHistory entities."""

from datetime import datetime
from typing import Any
from pydantic import BaseModel, ConfigDict, Field


class ClaimStatusHistoryResponse(BaseModel):
    id: str = Field(..., description="Unique status transition audit record ID")
    claim_id: str
    previous_status: str | None = None
    new_status: str
    transition_reason: str | None = None
    changed_by: str
    timestamp: datetime

    model_config = ConfigDict(from_attributes=True)

    def __getitem__(self, item: str) -> Any:
        return getattr(self, item)


class AuditEventResponse(BaseModel):
    id: str = Field(..., description="Unique audit event log ID (e.g. AUD-2026-000001)")
    entity_type: str
    entity_id: str
    action: str
    actor_type: str
    actor_id: str
    state_before: dict[str, Any] | None = None
    state_after: dict[str, Any] | None = None
    metadata_: dict[str, Any] | None = Field(default=None, alias="metadata_", serialization_alias="metadata")
    timestamp: datetime

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    def __getitem__(self, item: str) -> Any:
        return getattr(self, item)
