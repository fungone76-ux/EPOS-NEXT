"""Knowledge and belief containers kept separate from world truth."""

from pydantic import Field, JsonValue

from epos.domain.base import DomainModel


class KnowledgeState(DomainModel):
    """Facts known by one actor or held as canonical world truth."""

    facts: dict[str, JsonValue] = Field(default_factory=dict)
