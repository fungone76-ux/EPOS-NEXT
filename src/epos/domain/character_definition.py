"""Stable narrative canon used to keep NPC identity and voice consistent."""

from pydantic import Field

from epos.domain.base import DomainModel


class ExampleDialogue(DomainModel):
    """A voice demonstration, never a canned response."""

    player: str = Field(min_length=1, max_length=1000)
    npc: str = Field(min_length=1, max_length=2000)
    situation: str = Field(default="", max_length=500)


class ConditionalBehavior(DomainModel):
    """How stable character traits are expressed under a named condition."""

    condition: str = Field(min_length=1, max_length=120)
    guidance: tuple[str, ...] = ()


class NPCCharacterDefinition(DomainModel):
    """Character.AI-like stable definition, separate from mutable NPC state."""

    short_description: str = Field(default="", max_length=300)
    long_description: str = Field(default="", max_length=6000)
    personality: tuple[str, ...] = ()
    speech_style: str = Field(default="", max_length=2000)
    background: str = Field(default="", max_length=6000)
    likes: tuple[str, ...] = ()
    dislikes: tuple[str, ...] = ()
    desires: tuple[str, ...] = ()
    fears: tuple[str, ...] = ()
    goals: tuple[str, ...] = ()
    values: tuple[str, ...] = ()
    red_lines: tuple[str, ...] = ()
    relationship_tendencies: tuple[str, ...] = ()
    conditional_behaviors: tuple[ConditionalBehavior, ...] = ()
    example_dialogues: tuple[ExampleDialogue, ...] = ()
    never_behaviors: tuple[str, ...] = ()
