from __future__ import annotations

from collections.abc import Sequence

import pytest
from pydantic import ValidationError

from epos.application.actions.models import (
    ActionInterpretation,
    ActionInterpreterContext,
    CheckProposal,
    MovementProposal,
)
from epos.application.actions.service import ActionInterpreterService
from epos.application.actions.validation import ActionValidationError, ActionValidator
from epos.domain.ids import EntityId, LocationId, SkillId
from epos.domain.world_state import SkillDefinition


def _context(player_input: str = "Convincila a farmi entrare") -> ActionInterpreterContext:
    return ActionInterpreterContext(
        player_input=player_input,
        player_id=EntityId("player"),
        location_id=LocationId("lobby"),
        present_npc_ids=(EntityId("victoria"),),
        known_location_ids=(LocationId("lobby"), LocationId("office")),
        skill_catalog=(
            SkillDefinition(
                skill_id=SkillId("negoziazione"),
                name="Negoziazione",
                description="Persuasion and bargaining.",
                check_intents=("persuasion", "bargain"),
            ),
        ),
        player_skill_ratings={SkillId("negoziazione"): 4},
    )


def test_llm_action_contract_forbids_authoritative_dice_and_outcome() -> None:
    with pytest.raises(ValidationError):
        ActionInterpretation.model_validate(
            {
                "intent": "persuasion",
                "target_ids": ["victoria"],
                "movement": None,
                "check": {"skill_id": "negoziazione", "difficulty": 4},
                "outfit_request": None,
                "dice": [6, 6, 6],
                "outcome": "full_success",
            }
        )


def test_simple_dialogue_needs_no_check() -> None:
    action = ActionInterpretation(intent="dialogue", target_ids=(EntityId("victoria"),))

    validated = ActionValidator().validate(action, _context("Buona sera Victoria!"))

    assert validated.check is None
    assert validated.intent == "dialogue"


def test_offscene_target_is_rejected() -> None:
    action = ActionInterpretation(intent="dialogue", target_ids=(EntityId("stella"),))

    with pytest.raises(ActionValidationError, match="target.*stella"):
        ActionValidator().validate(action, _context())


def test_unknown_movement_destination_is_rejected() -> None:
    action = ActionInterpretation(
        intent="movement",
        movement=MovementProposal(destination_id=LocationId("secret_lab")),
    )

    with pytest.raises(ActionValidationError, match="location.*secret_lab"):
        ActionValidator().validate(action, _context())


def test_worldpack_mapping_requires_check_for_mapped_intent() -> None:
    action = ActionInterpretation(intent="persuasion", target_ids=(EntityId("victoria"),))

    with pytest.raises(ActionValidationError, match="requires a check"):
        ActionValidator().validate(action, _context())


def test_check_skill_must_exist_and_support_intent() -> None:
    unknown = ActionInterpretation(
        intent="persuasion",
        target_ids=(EntityId("victoria"),),
        check=CheckProposal(skill_id=SkillId("telepatia"), difficulty=4),
    )
    with pytest.raises(ActionValidationError, match="unknown skill"):
        ActionValidator().validate(unknown, _context())

    wrong_intent = ActionInterpretation(
        intent="dialogue",
        target_ids=(EntityId("victoria"),),
        check=CheckProposal(skill_id=SkillId("negoziazione"), difficulty=4),
    )
    with pytest.raises(ActionValidationError, match="does not support intent"):
        ActionValidator().validate(wrong_intent, _context())


def test_valid_worldpack_driven_check_is_accepted() -> None:
    action = ActionInterpretation(
        intent="persuasion",
        target_ids=(EntityId("victoria"),),
        check=CheckProposal(skill_id=SkillId("negoziazione"), difficulty=4),
    )

    validated = ActionValidator().validate(action, _context())

    assert validated.check is not None
    assert validated.check.skill_id == SkillId("negoziazione")
    assert validated.skill_rating == 4


class _InterpreterPort:
    def __init__(self, result: ActionInterpretation) -> None:
        self.result = result
        self.requests: list[ActionInterpreterContext] = []

    async def invoke(self, request: ActionInterpreterContext) -> ActionInterpretation:
        self.requests.append(request)
        return self.result


async def test_interpreter_service_calls_llm_boundary_then_python_validates() -> None:
    raw = ActionInterpretation(
        intent="persuasion",
        target_ids=(EntityId("victoria"),),
        check=CheckProposal(skill_id=SkillId("negoziazione"), difficulty=4),
    )
    port = _InterpreterPort(raw)
    service = ActionInterpreterService(port=port, validator=ActionValidator())
    context = _context()

    validated = await service.interpret(context)

    assert port.requests == [context]
    assert validated.skill_rating == 4
