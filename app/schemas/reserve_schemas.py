"""Pydantic schemas for Reserve entity."""

from datetime import datetime
from decimal import Decimal
from pydantic import AliasChoices, BaseModel, ConfigDict, Field


class ReserveResponse(BaseModel):
    id: str = Field(..., description="Unique reserve calculation ID (e.g. RES-CLM-2026-000001-001)")
    claim_id: str
    indemnity_reserve: Decimal = Field(
        ...,
        validation_alias=AliasChoices("estimated_indemnity_reserve", "indemnity_reserve"),
        description="Estimated loss indemnity reserve",
    )
    expense_reserve: Decimal = Field(
        ...,
        validation_alias=AliasChoices("estimated_expense_reserve", "expense_reserve"),
        description="Estimated loss adjustment expense (ALAE) reserve",
    )
    total_reserve: Decimal = Field(..., description="Total reserve allocated (indemnity + expense)")
    expense_ratio: Decimal = Field(default=Decimal("0.1200"), description="Expense loading percentage")
    calculation_method: str = Field(..., description="Actuarial calculation methodology")
    notes: str | None = Field(default=None, description="Optional reserve calculation notes")
    calculated_at: datetime
    calculated_by: str

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)
