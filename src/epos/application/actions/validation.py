"""Python-authoritative semantic/world validation for interpreted actions."""

from epos.application.actions.models import (
    ActionInterpretation,
    ActionInterpreterContext,
    IntimacyRequestProposal,
    OutfitRequestProposal,
    ValidatedAction,
    ValidatedIntimacyRequest,
    ValidatedOutfitRequest,
)
from epos.domain.errors import EposValidationError
from epos.domain.ids import EntityId


class ActionValidationError(EposValidationError):
    def __init__(self, message: str, *, code: str = "action.validation.failed") -> None:
        super().__init__(message, code=code)


class ActionValidator:
    """Authorize LLM proposals against the local scene and Worldpack skill catalog."""

    def validate(
        self,
        action: ActionInterpretation,
        context: ActionInterpreterContext,
    ) -> ValidatedAction:
        allowed_targets = {context.player_id, *context.present_npc_ids}
        for target_id in action.target_ids:
            if target_id not in allowed_targets:
                raise ActionValidationError(f"target {target_id} is not present in the local scene")

        if action.observation is not None:
            if action.observation.subject_id not in allowed_targets:
                raise ActionValidationError(
                    f"observation target {action.observation.subject_id} is not present"
                )
            if action.observation.subject_id not in action.target_ids:
                raise ActionValidationError("observation target must be included in target_ids")

        outfit_request = self._validate_outfit_request(
            action.outfit_request,
            action=action,
            context=context,
            allowed_targets=allowed_targets,
        )
        intimacy_request = self._validate_intimacy_request(
            action.intimacy_request,
            action=action,
            context=context,
            allowed_targets=allowed_targets,
        )

        if (
            action.movement is not None
            and action.movement.destination_id not in context.known_location_ids
        ):
            raise ActionValidationError(
                f"unknown location: {action.movement.destination_id}"
            )

        skills_by_id = {skill.skill_id: skill for skill in context.skill_catalog}
        mapped_skills = tuple(
            skill for skill in context.skill_catalog if action.intent in skill.check_intents
        )

        if action.check is None:
            # A declared observation focus is descriptive attention, not an
            # automatic challenge.  The same ``observe`` intent may still
            # carry an explicit Intuito check when the interpreter identifies
            # genuine uncertainty, concealment or risk.
            simple_observation = action.intent == "observe"
            if mapped_skills and not simple_observation:
                raise ActionValidationError(f"intent {action.intent} requires a check")
            return ValidatedAction(
                intent=action.intent,
                target_ids=action.target_ids,
                movement=action.movement,
                outfit_request=outfit_request,
                observation=action.observation,
                intimacy_request=intimacy_request,
            )

        skill = skills_by_id.get(action.check.skill_id)
        if skill is None:
            raise ActionValidationError(f"unknown skill: {action.check.skill_id}")
        if action.intent not in skill.check_intents:
            raise ActionValidationError(
                f"skill {skill.skill_id} does not support intent {action.intent}"
            )

        rating = context.player_skill_ratings.get(skill.skill_id)
        if rating is None or rating < 1:
            raise ActionValidationError(f"no positive player rating for skill {skill.skill_id}")

        return ValidatedAction(
            intent=action.intent,
            target_ids=action.target_ids,
            movement=action.movement,
            check=action.check,
            outfit_request=outfit_request,
            observation=action.observation,
            intimacy_request=intimacy_request,
            skill_rating=rating,
        )

    @staticmethod
    def _validate_intimacy_request(
        request: IntimacyRequestProposal | None,
        *,
        action: ActionInterpretation,
        context: ActionInterpreterContext,
        allowed_targets: set[EntityId],
    ) -> ValidatedIntimacyRequest | None:
        if request is None:
            return None
        if request.target_id == context.player_id:
            raise ActionValidationError("intimacy request must target another adult")
        if request.target_id not in allowed_targets:
            raise ActionValidationError(
                f"intimacy target {request.target_id} is not present"
            )
        if request.target_id not in action.target_ids:
            raise ActionValidationError("intimacy target must be included in target_ids")
        adults = set(context.adult_verified_entity_ids)
        if context.player_id not in adults:
            raise ActionValidationError("player is not adult verified")
        if request.target_id not in adults:
            raise ActionValidationError(
                f"intimacy target {request.target_id} is not adult verified"
            )
        return ValidatedIntimacyRequest.model_validate(request.model_dump(mode="python"))

    @staticmethod
    def _validate_outfit_request(
        request: OutfitRequestProposal | None,
        *,
        action: ActionInterpretation,
        context: ActionInterpreterContext,
        allowed_targets: set[EntityId],
    ) -> ValidatedOutfitRequest | None:
        if request is None:
            return None
        if request.target_id not in allowed_targets:
            raise ActionValidationError(f"outfit target {request.target_id} is not present")
        if request.target_id not in action.target_ids:
            raise ActionValidationError("outfit target must be included in target_ids")

        requested = request.requested_state
        legacy_item_ids = (request.item_id,) if request.item_id else ()
        item_ids = tuple(dict.fromkeys((*request.item_ids, *legacy_item_ids)))
        if requested in {"change", "wear", "wear_outfit", "change_outfit"} and (
            request.outfit_id is not None or request.semantic_tags
        ):
            requested = "wear_outfit"
        elif requested in {"remove", "take_off", "remove_items"}:
            requested = "remove_items"
        elif requested in {"put_on", "rewear", "rewear_items", "wear_items"} or (
            requested == "wear" and item_ids
        ):
            requested = "rewear_items"

        if requested == "wear_outfit":
            options = tuple(
                option
                for option in context.wardrobe_options
                if option.owner_id == request.target_id
            )
            required_tags = set(request.semantic_tags)
            candidates = tuple(
                option.outfit_id
                for option in options
                if (request.outfit_id is None or option.outfit_id == request.outfit_id)
                and required_tags.issubset(set(option.tags))
            )
            return ValidatedOutfitRequest(
                target_id=request.target_id,
                requested_state=requested,
                semantic_tags=request.semantic_tags,
                candidate_outfit_ids=candidates,
                requested_concept=request.outfit_id,
                allow_generated_outfit=not candidates,
            )

        if requested not in {"remove_items", "rewear_items"}:
            raise ActionValidationError(f"unsupported outfit request state: {requested}")
        if not item_ids:
            raise ActionValidationError("item outfit request requires at least one item_id")
        current = context.current_outfits.get(request.target_id)
        if current is None:
            raise ActionValidationError(f"no current outfit for {request.target_id}")
        by_id = {item.item_id: item for item in current.items}
        for item_id in item_ids:
            item = by_id.get(item_id)
            if item is None:
                raise ActionValidationError(f"unknown current outfit item: {item_id}")
            if requested == "remove_items" and not item.is_worn:
                raise ActionValidationError(f"outfit item is already removed: {item_id}")
            if requested == "rewear_items" and item.is_worn:
                raise ActionValidationError(f"outfit item is already worn: {item_id}")
        return ValidatedOutfitRequest(
            target_id=request.target_id,
            requested_state=requested,
            item_ids=item_ids,
        )
