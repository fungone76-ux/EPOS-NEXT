"""Build a small disclosure-safe narrator context from the canonical observable scene."""

from __future__ import annotations

from urllib.parse import quote

from epos.application.cognition.models import ValidatedNPCReaction
from epos.application.conversation.models import (
    ConversationFocus,
    NarratableMemory,
    NarrationContext,
    NarrationEvidence,
    NarrationEvidenceKind,
    NarrationKnowledgeSelection,
    NarrationKnowledgeSource,
    NarrationMode,
    NPCNarrationVoice,
)
from epos.application.visual.models import ObservableSceneState, SubjectKind
from epos.domain.errors import EposValidationError
from epos.domain.ids import EntityId, SceneId
from epos.domain.npc import NPCState
from epos.domain.relationships import RelationshipState
from epos.domain.world_state import WorldState

_CONVERSATIONAL_MODES = frozenset(
    {
        NarrationMode.BRIEF_SOCIAL,
        NarrationMode.DIRECT_DIALOGUE,
        NarrationMode.FOCUSED_INTERACTION,
    }
)


class NarrationContextError(EposValidationError):
    def __init__(self, message: str, *, code: str = "narration.context.invalid") -> None:
        super().__init__(message, code=code)


class NarrationContextBuilder:
    """Expose only material Python has explicitly authorized for narration."""

    def build(
        self,
        *,
        state: WorldState,
        scene: ObservableSceneState,
        focus: ConversationFocus,
        player_input: str,
        reactions: tuple[ValidatedNPCReaction, ...],
        knowledge_selections: tuple[NarrationKnowledgeSelection, ...] = (),
        narratable_memories: tuple[NarratableMemory, ...] = (),
    ) -> NarrationContext:
        self._validate_scene(state, scene, focus)
        reactions_by_npc = self._reaction_map(state, scene, reactions)
        if (
            focus.mode in _CONVERSATIONAL_MODES
            and focus.target_npc_id is not None
            and focus.target_npc_id not in reactions_by_npc
        ):
            raise NarrationContextError(
                "focused conversation target has no authorized NPC reaction"
            )
        if (
            focus.mode is NarrationMode.BRIEF_SOCIAL
            and focus.target_npc_id is None
            and not reactions_by_npc
        ):
            raise NarrationContextError(
                "open brief social narration has no authorized NPC reaction"
            )

        evidence = self._scene_evidence(scene)
        evidence.append(
            NarrationEvidence(
                evidence_id="player:declared_input",
                kind=NarrationEvidenceKind.PLAYER_DECLARATION,
                text=player_input,
                owner_id=state.player.entity_id,
            )
        )
        evidence.append(
            NarrationEvidence(
                evidence_id="action:resolved",
                kind=NarrationEvidenceKind.ACTION_RESULT,
                text=scene.resolved_action.action.model_dump_json(),
            )
        )
        resolved_check = scene.resolved_action.resolved_check
        if resolved_check is not None:
            evidence.append(
                NarrationEvidence(
                    evidence_id="check:resolved",
                    kind=NarrationEvidenceKind.CHECK_RESULT,
                    text=resolved_check.model_dump_json(),
                )
            )

        for reaction in reactions:
            evidence.extend(self._reaction_evidence(state, reaction))

        evidence.extend(
            self._knowledge_evidence(
                state=state,
                reactions_by_npc=reactions_by_npc,
                selections=knowledge_selections,
            )
        )
        evidence.extend(
            self._memory_evidence(
                reactions_by_npc=reactions_by_npc,
                memories=narratable_memories,
            )
        )
        self._ensure_unique_evidence(evidence)

        voices = tuple(
            self._voice(state.npcs[npc_id], state.player.entity_id)
            for npc_id in sorted(reactions_by_npc, key=str)
        )
        return NarrationContext(
            player_id=state.player.entity_id,
            player_input=player_input,
            focus=focus.model_copy(deep=True),
            scene=scene.model_copy(deep=True),
            reactions=tuple(reaction.model_copy(deep=True) for reaction in reactions),
            voices=voices,
            evidence=tuple(evidence),
        )

    @staticmethod
    def _validate_scene(
        state: WorldState,
        scene: ObservableSceneState,
        focus: ConversationFocus,
    ) -> None:
        if focus.speaker_id != state.player.entity_id:
            raise NarrationContextError("conversation focus speaker is not the player")
        if scene.session_id != state.session_id:
            raise NarrationContextError("narration scene belongs to another session")
        if scene.worldpack_id != state.worldpack_id:
            raise NarrationContextError("narration scene belongs to another worldpack")
        if scene.scene_id != SceneId(f"{state.session_id}:{int(state.turn_number)}"):
            raise NarrationContextError("narration scene id does not match authoritative turn")
        if scene.time.turn_number != state.turn_number:
            raise NarrationContextError("narration scene turn does not match authoritative state")
        if scene.time.day != state.day or scene.time.world_phase != state.world_phase:
            raise NarrationContextError("narration scene time does not match authoritative state")
        if scene.location.location_id != state.player.location_id:
            raise NarrationContextError("narration scene does not match player location")

        subjects = {subject.entity_id: subject for subject in scene.visible_subjects}
        local_ids = {
            state.player.entity_id,
            *(
                npc_id
                for npc_id, npc in state.npcs.items()
                if npc.location_id == state.player.location_id
            ),
        }
        subject_ids = set(subjects)
        if state.player.entity_id not in subject_ids:
            raise NarrationContextError("player is missing from narration scene")
        invalid_subject_ids = subject_ids - local_ids
        if invalid_subject_ids:
            invalid_id = min(invalid_subject_ids, key=str)
            raise NarrationContextError(
                "narration scene contains subject outside authoritative local presence: "
                f"{invalid_id}"
            )

        player_subject = subjects[state.player.entity_id]
        if player_subject.kind is not SubjectKind.PLAYER:
            raise NarrationContextError("player is not marked as player in narration scene")
        expected_player_name = state.player.name.strip()
        if expected_player_name.casefold() in {"protagonista", "player", "giocatore"}:
            expected_player_name = "player"
        if (
            player_subject.name != expected_player_name
            or player_subject.outfit != state.player.outfit
            or player_subject.visual_state != state.player.visual_state
        ):
            raise NarrationContextError("player observable state is not authoritative")

        for npc_id, subject in subjects.items():
            if npc_id == state.player.entity_id:
                continue
            npc = state.npcs.get(npc_id)
            if npc is None or npc.location_id != state.player.location_id:
                raise NarrationContextError(
                    f"visible NPC {npc_id} is not in authoritative local presence"
                )
            if subject.kind is not SubjectKind.NPC:
                raise NarrationContextError(f"visible NPC {npc_id} has invalid subject kind")
            if (
                subject.name != npc.identity.name
                or subject.role != npc.identity.role
                or subject.outfit != npc.outfit
                or subject.visual_state != npc.visual_state
            ):
                raise NarrationContextError(
                    f"visible NPC {npc_id} observable state is not authoritative"
                )

        if focus.target_npc_id is not None and focus.target_npc_id not in subjects:
            raise NarrationContextError(
                "conversation focus target is not present in narration scene"
            )

    @staticmethod
    def _reaction_map(
        state: WorldState,
        scene: ObservableSceneState,
        reactions: tuple[ValidatedNPCReaction, ...],
    ) -> dict[EntityId, ValidatedNPCReaction]:
        result: dict[EntityId, ValidatedNPCReaction] = {}
        visible_npc_ids = {
            subject.entity_id
            for subject in scene.visible_subjects
            if subject.kind is SubjectKind.NPC
        }
        for reaction in reactions:
            npc = state.npcs.get(reaction.npc_id)
            if npc is None:
                raise NarrationContextError(
                    f"reaction references unknown NPC {reaction.npc_id}"
                )
            if (
                reaction.npc_id not in visible_npc_ids
                or npc.location_id != state.player.location_id
            ):
                raise NarrationContextError(
                    f"reacting NPC {reaction.npc_id} is not present"
                )
            if reaction.npc_id in result:
                raise NarrationContextError(
                    f"duplicate reaction for NPC {reaction.npc_id}"
                )
            result[reaction.npc_id] = reaction
        return result

    @staticmethod
    def _scene_evidence(scene: ObservableSceneState) -> list[NarrationEvidence]:
        evidence = [
            NarrationEvidence(
                evidence_id="scene:location",
                kind=NarrationEvidenceKind.OBSERVABLE,
                text=scene.location.model_dump_json(),
            ),
            NarrationEvidence(
                evidence_id="scene:time",
                kind=NarrationEvidenceKind.OBSERVABLE,
                text=scene.time.model_dump_json(),
            ),
        ]
        for subject in scene.visible_subjects:
            evidence.append(
                NarrationEvidence(
                    evidence_id=(
                        f"scene:subject:{NarrationContextBuilder._part(subject.entity_id)}"
                    ),
                    kind=NarrationEvidenceKind.OBSERVABLE,
                    text=subject.model_dump_json(),
                )
            )
        for consequence in scene.observable_consequences:
            evidence.append(
                NarrationEvidence(
                    evidence_id=(
                        f"scene:consequence:{NarrationContextBuilder._part(consequence.consequence_id)}"
                    ),
                    kind=NarrationEvidenceKind.OBSERVABLE,
                    text=consequence.fact,
                )
            )
        return evidence

    @staticmethod
    def _reaction_evidence(
        state: WorldState,
        reaction: ValidatedNPCReaction,
    ) -> list[NarrationEvidence]:
        evidence = [
            NarrationEvidence(
                evidence_id=f"reaction:{NarrationContextBuilder._part(reaction.npc_id)}",
                kind=NarrationEvidenceKind.NPC_REACTION,
                text=reaction.model_dump_json(),
                owner_id=reaction.npc_id,
            )
        ]
        for secret_id in reaction.authorized_secret_disclosures:
            npc = state.npcs[reaction.npc_id]
            secret = next(
                (item for item in npc.secrets if item.secret_id == secret_id),
                None,
            )
            if secret is None:
                raise NarrationContextError(
                    f"authorized secret is missing from NPC state: {secret_id}"
                )
            evidence.append(
                NarrationEvidence(
                    evidence_id=(
                        f"npc:{NarrationContextBuilder._part(reaction.npc_id)}:secret:"
                        f"{NarrationContextBuilder._part(secret_id)}"
                    ),
                    kind=NarrationEvidenceKind.AUTHORIZED_SECRET,
                    text=secret.fact,
                    owner_id=reaction.npc_id,
                )
            )
        return evidence

    @staticmethod
    def _knowledge_evidence(
        *,
        state: WorldState,
        reactions_by_npc: dict[EntityId, ValidatedNPCReaction],
        selections: tuple[NarrationKnowledgeSelection, ...],
    ) -> list[NarrationEvidence]:
        evidence: list[NarrationEvidence] = []
        for selection in selections:
            if selection.npc_id not in reactions_by_npc:
                raise NarrationContextError(
                    f"knowledge selection has no authorized reaction: {selection.npc_id}"
                )
            npc = state.npcs[selection.npc_id]
            source = (
                npc.knowledge
                if selection.source is NarrationKnowledgeSource.KNOWLEDGE
                else npc.beliefs
            )
            kind = (
                NarrationEvidenceKind.NPC_KNOWLEDGE
                if selection.source is NarrationKnowledgeSource.KNOWLEDGE
                else NarrationEvidenceKind.NPC_BELIEF
            )
            for key in selection.keys:
                value = source.facts.get(key)
                if value is None:
                    raise NarrationContextError(
                        f"selected NPC knowledge is missing: {selection.npc_id}:{key}"
                    )
                evidence.append(
                    NarrationEvidence(
                        evidence_id=(
                            f"npc:{NarrationContextBuilder._part(selection.npc_id)}:"
                            f"{selection.source.value}:{NarrationContextBuilder._part(key)}"
                        ),
                        kind=kind,
                        text=value,
                        owner_id=selection.npc_id,
                    )
                )
        return evidence

    @staticmethod
    def _memory_evidence(
        *,
        reactions_by_npc: dict[EntityId, ValidatedNPCReaction],
        memories: tuple[NarratableMemory, ...],
    ) -> list[NarrationEvidence]:
        evidence: list[NarrationEvidence] = []
        for item in memories:
            reaction = reactions_by_npc.get(item.owner_id)
            if reaction is None or item.memory.memory_id not in reaction.referenced_memory_ids:
                raise NarrationContextError(
                    f"narratable memory is not authorized by reaction: {item.owner_id}"
                )
            evidence.append(
                NarrationEvidence(
                    evidence_id=(
                        f"npc:{NarrationContextBuilder._part(item.owner_id)}:memory:"
                        f"{NarrationContextBuilder._part(item.memory.memory_id)}"
                    ),
                    kind=NarrationEvidenceKind.NPC_MEMORY,
                    text=item.memory.summary,
                    owner_id=item.owner_id,
                )
            )
        return evidence

    @staticmethod
    def _voice(npc: NPCState, player_id: EntityId) -> NPCNarrationVoice:
        relationship = npc.relationships.get(player_id, RelationshipState())
        return NPCNarrationVoice(
            npc_id=npc.identity.entity_id,
            name=npc.identity.name,
            personality=npc.personality,
            speech_style=npc.speech_style,
            emotional_state=npc.emotional_state.model_copy(deep=True),
            relationship_with_player=relationship.model_copy(deep=True),
            character_definition=(
                None
                if npc.character_definition is None
                else npc.character_definition.model_copy(deep=True)
            ),
        )

    @staticmethod
    def _ensure_unique_evidence(evidence: list[NarrationEvidence]) -> None:
        ids = [item.evidence_id for item in evidence]
        if len(ids) != len(set(ids)):
            raise NarrationContextError("narration evidence ids must be unique")

    @staticmethod
    def _part(value: object) -> str:
        return quote(str(value), safe="")