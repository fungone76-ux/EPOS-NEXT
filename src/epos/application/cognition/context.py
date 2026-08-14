"""Build small private cognition contexts from authoritative NPC-owned state."""

from __future__ import annotations

from pydantic import Field

from epos.application.actions.models import ResolvedCheck, ValidatedAction
from epos.application.cognition.models import (
    CognitionScene,
    PrivateCognitiveContext,
    SecretCognitiveState,
)
from epos.application.memory import MemoryRecallResult
from epos.domain.base import DomainModel
from epos.domain.errors import EposValidationError
from epos.domain.ids import EntityId
from epos.domain.intimacy import IntimacyState
from epos.domain.memory import MemoryEntryState
from epos.domain.npc import DisclosureRule, NPCState, SecretState
from epos.domain.relationships import RelationshipState
from epos.domain.world_state import WorldState


class CognitionContextError(EposValidationError):
    def __init__(self, message: str, *, code: str = "cognition.context.invalid") -> None:
        super().__init__(message, code=code)


class CognitionContextPolicy(DomainModel):
    short_term_limit: int = Field(default=8, ge=1, le=20)
    core_limit: int = Field(default=6, ge=1, le=12)


class PrivateCognitiveContextBuilder:
    def __init__(self, policy: CognitionContextPolicy | None = None) -> None:
        self._policy = policy or CognitionContextPolicy()

    def build(
        self,
        *,
        state: WorldState,
        npc_id: EntityId,
        scene: CognitionScene,
        player_input: str,
        action: ValidatedAction,
        recalled: MemoryRecallResult,
        resolved_check: ResolvedCheck | None,
    ) -> PrivateCognitiveContext:
        npc = state.npcs.get(npc_id)
        if npc is None:
            raise CognitionContextError(f"unknown NPC: {npc_id}")
        if npc.location_id != state.player.location_id:
            raise CognitionContextError(f"NPC {npc_id} is not present with the player")
        if scene.location_id != state.player.location_id:
            raise CognitionContextError("cognition scene does not match player location")
        if npc_id not in scene.present_entity_ids:
            raise CognitionContextError(f"NPC {npc_id} is missing from cognition scene")

        relationship = npc.relationships.get(state.player.entity_id, RelationshipState())
        return PrivateCognitiveContext(
            npc_id=npc.identity.entity_id,
            npc_name=npc.identity.name,
            role=npc.identity.role,
            player_id=state.player.entity_id,
            personality=npc.personality,
            speech_style=npc.speech_style,
            desires=npc.desires,
            goals=npc.goals,
            fears=npc.fears,
            red_lines=npc.red_lines,
            current_intentions=npc.intentions,
            emotional_state=npc.emotional_state.model_copy(deep=True),
            relationship_with_player=relationship.model_copy(deep=True),
            bond_state=npc.bond_state.model_copy(deep=True),
            intimacy_with_player=self._intimacy(npc, state.player.entity_id),
            knowledge=npc.knowledge.model_copy(deep=True),
            beliefs=npc.beliefs.model_copy(deep=True),
            false_beliefs=npc.false_beliefs.model_copy(deep=True),
            discoveries=npc.discoveries.model_copy(deep=True),
            core_memories=self._core_memories(npc),
            short_term_memories=npc.short_term_memory[-self._policy.short_term_limit :],
            recalled_memories=recalled.memories,
            secrets=self._secrets(npc, state=state, relationship=relationship),
            scene=scene.model_copy(deep=True),
            player_input=player_input,
            action=action.model_copy(deep=True),
            resolved_check=None if resolved_check is None else resolved_check.model_copy(deep=True),
        )

    def _core_memories(self, npc: NPCState) -> tuple[MemoryEntryState, ...]:
        ranked = sorted(
            npc.core_memories,
            key=lambda memory: (-memory.salience, -int(memory.turn), str(memory.memory_id)),
        )
        return tuple(ranked[: self._policy.core_limit])

    @staticmethod
    def _intimacy(npc: NPCState, player_id: EntityId) -> IntimacyState | None:
        value = npc.intimacy.get(player_id)
        return None if value is None else value.model_copy(deep=True)

    @staticmethod
    def _secrets(
        npc: NPCState,
        *,
        state: WorldState,
        relationship: RelationshipState,
    ) -> tuple[SecretCognitiveState, ...]:
        rules = {rule.secret_id: rule for rule in npc.disclosure_rules}
        return tuple(
            SecretCognitiveState(
                secret_id=secret.secret_id,
                fact=secret.fact,
                disclosure_allowed=PrivateCognitiveContextBuilder._allowed(
                    secret,
                    rules.get(secret.secret_id),
                    state=state,
                    relationship=relationship,
                ),
            )
            for secret in npc.secrets
        )

    @staticmethod
    def _allowed(
        secret: SecretState,
        rule: DisclosureRule | None,
        *,
        state: WorldState,
        relationship: RelationshipState,
    ) -> bool:
        del secret
        if rule is None:
            return False
        if any(not state.flags.get(flag, False) for flag in rule.required_flags):
            return False
        return rule.trust_min is None or relationship.trust >= rule.trust_min
