"""Typed contracts for conversation focus and safe narration."""

from __future__ import annotations

import re
from enum import StrEnum
from typing import Annotated, Literal

from pydantic import Field, field_validator

from epos.application.actions.models import ResolvedCheck, ValidatedAction
from epos.application.cognition.models import CognitionScene, ValidatedNPCReaction
from epos.domain.base import DomainModel
from epos.domain.ids import EntityId, LocationId
from epos.domain.memory import MemoryEntryState
from epos.domain.psychology import EmotionalState
from epos.domain.relationships import RelationshipState
from epos.domain.world_state import WorldState

_SEMANTIC_TOKEN = re.compile(r"^[a-z0-9][a-z0-9_.:-]*$")
_EVIDENCE_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.:%-]*$")


def _token(value: str, *, field_name: str) -> str:
    normalized = value.strip().casefold()
    if not _SEMANTIC_TOKEN.fullmatch(normalized):
        raise ValueError(f"{field_name} must be one semantic token")
    return normalized


def _non_empty(value: str, *, field_name: str) -> str:
    normalized = value.strip()
    if not normalized:
        raise ValueError(f"{field_name} must not be empty")
    return normalized


class NarrationMode(StrEnum):
    BRIEF_SOCIAL = "brief_social"
    DIRECT_DIALOGUE = "direct_dialogue"
    FOCUSED_INTERACTION = "focused_interaction"
    ACTION = "action"
    EXPLORATION = "exploration"
    DRAMATIC_SCENE = "dramatic_scene"


class ConversationFocusContext(DomainModel):
    """Small semantic-classification context; it does not contain private NPC state."""

    player_id: EntityId
    player_input: str
    location_id: LocationId
    present_npc_ids: tuple[EntityId, ...] = ()
    npc_names: dict[EntityId, str] = Field(default_factory=dict)
    action: ValidatedAction

    @classmethod
    def from_world_state(
        cls,
        state: WorldState,
        *,
        player_input: str,
        action: ValidatedAction,
    ) -> ConversationFocusContext:
        present = tuple(
            sorted(
                (
                    npc_id
                    for npc_id, npc in state.npcs.items()
                    if npc.location_id == state.player.location_id
                ),
                key=str,
            )
        )
        names = {npc_id: state.npcs[npc_id].identity.name for npc_id in present}
        return cls(
            player_id=state.player.entity_id,
            player_input=player_input,
            location_id=state.player.location_id,
            present_npc_ids=present,
            npc_names=names,
            action=action.model_copy(deep=True),
        )


class ConversationFocusProposal(DomainModel):
    """Untrusted semantic focus proposed by the classifier LLM."""

    speaker_id: EntityId
    target_npc_id: EntityId | None = None
    topic: str
    mode: NarrationMode

    @field_validator("topic")
    @classmethod
    def normalize_topic(cls, value: str) -> str:
        return _token(value, field_name="topic")


class ConversationFocus(DomainModel):
    """Python-validated focus used to control pacing and dialogue priority."""

    speaker_id: EntityId
    target_npc_id: EntityId | None = None
    topic: str
    mode: NarrationMode

    @field_validator("topic")
    @classmethod
    def normalize_topic(cls, value: str) -> str:
        return _token(value, field_name="topic")


class NarrationKnowledgeSource(StrEnum):
    KNOWLEDGE = "knowledge"
    BELIEF = "belief"
    FALSE_BELIEF = "false_belief"
    DISCOVERY = "discovery"


class NarrationKnowledgeSelection(DomainModel):
    """Python-owned whitelist selecting which NPC facts may enter narration context."""

    npc_id: EntityId
    source: NarrationKnowledgeSource
    keys: tuple[str, ...] = ()


class NarratableMemory(DomainModel):
    """Explicit Python authorization to expose one memory to the narrator."""

    owner_id: EntityId
    memory: MemoryEntryState


class NarrationEvidenceKind(StrEnum):
    OBSERVABLE = "observable"
    PLAYER_DECLARATION = "player_declaration"
    ACTION_RESULT = "action_result"
    CHECK_RESULT = "check_result"
    NPC_REACTION = "npc_reaction"
    NPC_KNOWLEDGE = "npc_knowledge"
    NPC_BELIEF = "npc_belief"
    NPC_FALSE_BELIEF = "npc_false_belief"
    NPC_DISCOVERY = "npc_discovery"
    NPC_MEMORY = "npc_memory"
    AUTHORIZED_SECRET = "authorized_secret"


class NarrationEvidence(DomainModel):
    """One item the narrator is allowed to use, with ownership preserved."""

    evidence_id: str
    kind: NarrationEvidenceKind
    text: str
    owner_id: EntityId | None = None

    @field_validator("evidence_id")
    @classmethod
    def validate_evidence_id(cls, value: str) -> str:
        normalized = value.strip()
        if not _EVIDENCE_ID.fullmatch(normalized):
            raise ValueError("evidence_id must be a stable token")
        return normalized

    @field_validator("text")
    @classmethod
    def validate_text(cls, value: str) -> str:
        return _non_empty(value, field_name="evidence text")


class NPCNarrationVoice(DomainModel):
    """Narrator-facing public voice/psychology summary for one reacting NPC."""

    npc_id: EntityId
    name: str
    personality: tuple[str, ...] = ()
    speech_style: str = ""
    emotional_state: EmotionalState
    relationship_with_player: RelationshipState


class NarrationContext(DomainModel):
    """Disclosure-safe context passed to the narration LLM."""

    player_id: EntityId
    player_input: str
    focus: ConversationFocus
    scene: CognitionScene
    action: ValidatedAction
    resolved_check: ResolvedCheck | None = None
    reactions: tuple[ValidatedNPCReaction, ...] = ()
    voices: tuple[NPCNarrationVoice, ...] = ()
    evidence: tuple[NarrationEvidence, ...] = ()


class NPCDialogueDraft(DomainModel):
    """Natural-language NPC speech. There is deliberately no player-dialogue equivalent."""

    kind: Literal["npc_dialogue"] = "npc_dialogue"
    speaker_id: EntityId
    text: str
    evidence_ids: tuple[str, ...] = ()

    @field_validator("text")
    @classmethod
    def validate_text(cls, value: str) -> str:
        return _non_empty(value, field_name="dialogue text")


class WorldNarrationDraft(DomainModel):
    """External narration grounded only in already-authorized world evidence."""

    kind: Literal["world_narration"] = "world_narration"
    text: str
    evidence_ids: tuple[str, ...] = ()
    subject_ids: tuple[EntityId, ...] = ()

    @field_validator("text")
    @classmethod
    def validate_text(cls, value: str) -> str:
        return _non_empty(value, field_name="world narration text")


NarrationUnit = Annotated[
    NPCDialogueDraft | WorldNarrationDraft,
    Field(discriminator="kind"),
]


class NarrationProposal(DomainModel):
    """Untrusted structured narration produced by the narration LLM."""

    units: tuple[NarrationUnit, ...]


class ValidatedNarration(DomainModel):
    """Narration units accepted by Python authority checks."""

    units: tuple[NarrationUnit, ...]


class NarrationResult(DomainModel):
    """Player-facing text plus its validated structured representation."""

    focus: ConversationFocus
    units: tuple[NarrationUnit, ...]
    text: str
