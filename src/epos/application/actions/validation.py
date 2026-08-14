"""Python-authoritative semantic/world validation for interpreted actions."""

from epos.application.actions.models import (
    ActionInterpretation,
    ActionInterpreterContext,
    ValidatedAction,
)
from epos.domain.errors import EposValidationError


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
            if mapped_skills:
                raise ActionValidationError(f"intent {action.intent} requires a check")
            return ValidatedAction(
                intent=action.intent,
                target_ids=action.target_ids,
                movement=action.movement,
                outfit_request=action.outfit_request,
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
            outfit_request=action.outfit_request,
            skill_rating=rating,
        )
