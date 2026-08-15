"""Python authorization for untrusted NPC cognition proposals."""

from epos.application.cognition.models import (
    NPCReactionProposal,
    OutfitRequestDisposition,
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
                raise CognitionValidationError(
                    f"memory {memory_id} is not available to this cognition"
                )

        secret_permissions = {
            secret.secret_id: secret.disclosure_allowed for secret in context.secrets
        }
        for secret_id in proposal.requested_secret_disclosures:
            if not secret_permissions.get(secret_id, False):
                raise CognitionValidationError(
                    f"secret {secret_id} is not authorized for disclosure"
                )

        self._validate_outfit_response(proposal, context)
        self._validate_autonomous_outfit_action(proposal, context)
        self._validate_intimacy_response(proposal, context)

        return ValidatedNPCReaction(
            npc_id=proposal.npc_id,
            intent=proposal.intent,
            speech_act=proposal.speech_act,
            topic_tags=proposal.topic_tags,
            emotional_tone=proposal.emotional_tone,
            action_intent=proposal.action_intent,
            target_ids=proposal.target_ids,
            referenced_memory_ids=proposal.referenced_memory_ids,
            authorized_secret_disclosures=proposal.requested_secret_disclosures,
            outfit_request_response=proposal.outfit_request_response,
            autonomous_outfit_action=proposal.autonomous_outfit_action,
            intimacy_response=proposal.intimacy_response,
        )

    @staticmethod
    def _validate_intimacy_response(
        proposal: NPCReactionProposal,
        context: PrivateCognitiveContext,
    ) -> None:
        response = proposal.intimacy_response
        request = context.action.intimacy_request
        targets_this_npc = request is not None and request.target_id == context.npc_id
        if not targets_this_npc:
            if response is not None:
                raise CognitionValidationError(
                    "NPC cannot answer another actor's intimacy request"
                )
            return
        if response is None:
            raise CognitionValidationError(
                "target NPC must explicitly answer intimacy request"
            )
        if request is None or response.scope is not request.scope:
            raise CognitionValidationError(
                "NPC intimacy response does not match the requested scope"
            )

    @staticmethod
    def _validate_outfit_response(
        proposal: NPCReactionProposal,
        context: PrivateCognitiveContext,
    ) -> None:
        response = proposal.outfit_request_response
        request = context.action.outfit_request
        targets_this_npc = request is not None and request.target_id == context.npc_id
        if not targets_this_npc:
            if response is not None:
                raise CognitionValidationError("NPC cannot answer another actor's outfit request")
            return
        if response is None:
            raise CognitionValidationError("target NPC must explicitly answer outfit request")

        if response.disposition is OutfitRequestDisposition.REJECTED:
            if response.selected_outfit_id is not None or response.generated_outfit is not None:
                raise CognitionValidationError(
                    "rejected outfit request cannot select or generate an outfit"
                )
            return
        if request is None:
            raise CognitionValidationError("outfit response has no validated request")
        if request.requested_state == "wear_outfit":
            selected = response.selected_outfit_id
            generated = response.generated_outfit
            if request.candidate_outfit_ids:
                if generated is not None:
                    raise CognitionValidationError(
                        "NPC cannot generate an outfit while canonical candidates exist"
                    )
                if selected is None or selected not in request.candidate_outfit_ids:
                    raise CognitionValidationError(
                        "NPC outfit choice is not one of the Python-authorized candidates"
                    )
            elif request.allow_generated_outfit:
                if selected is not None or generated is None:
                    raise CognitionValidationError(
                        "missing outfit requires exactly one structured generated outfit"
                    )
            else:
                raise CognitionValidationError(
                    "outfit request has neither candidates nor generation permission"
                )
        elif response.selected_outfit_id is not None or response.generated_outfit is not None:
            raise CognitionValidationError(
                "item-state request cannot select or generate a full outfit"
            )

    @staticmethod
    def _validate_autonomous_outfit_action(
        proposal: NPCReactionProposal,
        context: PrivateCognitiveContext,
    ) -> None:
        action = proposal.autonomous_outfit_action
        if action is None:
            return
        if proposal.outfit_request_response is not None:
            raise CognitionValidationError(
                "NPC cannot combine a request response and autonomous outfit action"
            )
        if action.requested_state == "wear_outfit":
            if action.outfit_id not in context.available_outfit_ids:
                raise CognitionValidationError("NPC selected an unavailable canonical outfit")
            if action.item_ids:
                raise CognitionValidationError("full outfit action cannot also name item_ids")
            return
        if action.outfit_id is not None or not action.item_ids:
            raise CognitionValidationError("item outfit action requires item_ids only")
        current = {item.item_id: item for item in context.current_outfit.items}
        for item_id in action.item_ids:
            item = current.get(item_id)
            if item is None:
                raise CognitionValidationError(f"NPC selected unknown outfit item {item_id}")
            if action.requested_state == "remove_items" and not item.is_worn:
                raise CognitionValidationError(f"NPC outfit item is already removed: {item_id}")
            if action.requested_state == "rewear_items" and item.is_worn:
                raise CognitionValidationError(f"NPC outfit item is already worn: {item_id}")
