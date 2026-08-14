"""Python authorization for untrusted NPC cognition proposals."""

from epos.application.cognition.models import (
    NPCReactionProposal,
    PrivateCognitiveContext,
    ValidatedNPCReaction,
)
from epos.domain.errors import EposValidationError


class CognitionValidationError(EposValidationError):
    def __init__(self, message: str, *, code: str = "cognition.reaction.invalid") -> None:
        super().__init__(message, code=code)


class NPCReactionValidator:
    def validate(
        self,
        proposal: NPCReactionProposal,
        context: PrivateCognitiveContext,
    ) -> ValidatedNPCReaction:
        if proposal.npc_id != context.npc_id:
            raise CognitionValidationError(
                f"reaction NPC {proposal.npc_id} does not match context NPC {context.npc_id}"
            )

        present_ids = set(context.scene.present_entity_ids)
        for target_id in proposal.target_ids:
            if target_id not in present_ids:
                raise CognitionValidationError(f"reaction target {target_id} is not present")

        available_memory_ids = {
            *(memory.memory_id for memory in context.core_memories),
            *(memory.memory_id for memory in context.short_term_memories),
            *(ranked.memory.memory_id for ranked in context.recalled_memories),
        }
        for memory_id in proposal.referenced_memory_ids:
            if memory_id not in available_memory_ids:
                raise CognitionValidationError(f"memory {memory_id} is not available to this cognition")

        secret_permissions = {
            secret.secret_id: secret.disclosure_allowed for secret in context.secrets
        }
        for secret_id in proposal.requested_secret_disclosures:
            if not secret_permissions.get(secret_id, False):
                raise CognitionValidationError(f"secret {secret_id} is not authorized for disclosure")

        return ValidatedNPCReaction(
            npc_id=proposal.npc_id,
            intent=proposal.intent,
            communication_goal=proposal.communication_goal,
            emotional_tone=proposal.emotional_tone,
            observable_action=proposal.observable_action,
            target_ids=proposal.target_ids,
            referenced_memory_ids=proposal.referenced_memory_ids,
            authorized_secret_disclosures=proposal.requested_secret_disclosures,
        )
