from __future__ import annotations

from pathlib import Path

from epos.application.actions.models import ActionInterpretation, ActionInterpreterContext, CheckProposal
from epos.application.actions.validation import ActionValidator
from epos.domain.ids import EntityId, SkillId
from epos.infrastructure.worldpacks.loader import FileSystemWorldpackLoader


async def test_two_worldpacks_drive_different_skill_checks_without_core_changes() -> None:
    root = Path(__file__).resolve().parents[2] / "worldpacks"
    loader = FileSystemWorldpackLoader()
    resort = await loader.load(root / "resort_world", session_id="resort-check")
    bronze = await loader.load(root / "test_world", session_id="bronze-check")

    resort_state = resort.world_state
    resort_context = ActionInterpreterContext.from_world_state(
        resort_state,
        player_input="Convincila a farmi entrare",
        known_location_ids=tuple(resort_state.locations),
    )
    resort_action = ActionInterpretation(
        intent="persuasion",
        target_ids=(EntityId("victoria"),),
        check=CheckProposal(skill_id=SkillId("negoziazione"), difficulty=4),
    )

    bronze_state = bronze.world_state
    bronze_context = ActionInterpreterContext.from_world_state(
        bronze_state,
        player_input="Affronto Theron con la sarissa",
        known_location_ids=tuple(bronze_state.locations),
    )
    bronze_action = ActionInterpretation(
        intent="combat",
        target_ids=(EntityId("theron"),),
        check=CheckProposal(skill_id=SkillId("sarissa"), difficulty=4),
    )

    resort_validated = ActionValidator().validate(resort_action, resort_context)
    bronze_validated = ActionValidator().validate(bronze_action, bronze_context)

    assert resort_validated.skill_rating == 4
    assert bronze_validated.skill_rating == 3
    assert SkillId("sarissa") not in resort_state.skill_definitions
    assert SkillId("negoziazione") not in bronze_state.skill_definitions
