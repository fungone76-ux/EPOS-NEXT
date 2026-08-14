"""Shared Pydantic configuration for authoritative domain state."""

from pydantic import BaseModel, ConfigDict


class DomainModel(BaseModel):
    """Base model for validated EPOS domain state."""

    model_config = ConfigDict(extra="forbid", validate_assignment=True)
