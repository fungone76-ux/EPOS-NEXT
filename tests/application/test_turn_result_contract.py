from __future__ import annotations

from epos.application.actions import CheckOutcome, ResolvedCheck, ValidatedAction
from epos.application.conversation import (
    ConversationFocus,
    NarrationMode,
    NarrationResult,
    NPCDialogueDraft,
)
from epos.application.results import TurnResultMapper
from epos.application.turn import PostCommitIssue, TurnOrchestrationResult
from epos.application.visual import ObservableSceneState
from epos.domain.ids import EntityId, SceneId, SessionId, SkillId, TurnNumber
from epos.domain.world_state import WorldState


def _internal_result(*, visual_issue: bool = False) -> TurnOrchestrationResult:
    state = WorldState.model_construct(
        session_id=SessionId("session-1"),
        turn_number=TurnNumber(12),
    )
    action = ValidatedAction(intent="persuade")
    scene = ObservableSceneState.model_construct(scene_id=SceneId("session-1:12"))
    focus = ConversationFocus(
        speaker_id=EntityId("player"),
        target_npc_id=EntityId("luna"),
        topic="outfit",
        mode=NarrationMode.DIRECT_DIALOGUE,
    )
    narration = NarrationResult(
        focus=focus,
        units=(
            NPCDialogueDraft(
                speaker_id=EntityId("luna"),
                text="Va bene.",
            ),
        ),
        text='Luna annuisce. “Va bene.”',
    )
    check = ResolvedCheck(
        skill_id=SkillId("persuasion"),
        difficulty=4,
        rating=3,
        pool_size=3,
        dice=(6, 4, 2),
        success_count=2,
        outcome=CheckOutcome.FULL_SUCCESS,
    )
    return TurnOrchestrationResult.model_construct(
        committed_state=state,
        action=action,
        resolved_check=check,
        scene=scene,
        narration=narration,
        visual=None,
        memory_stored=True,
        post_commit_issues=(
            (
                PostCommitIssue(
                    phase="visual",
                    code="renderer.offline",
                    message="Renderer offline",
                ),
            )
            if visual_issue
            else ()
        ),
    )


def test_turn_result_is_stable_and_excludes_authoritative_world_state() -> None:
    public = TurnResultMapper.map(_internal_result())

    assert public.session_id == SessionId("session-1")
    assert public.turn_number == TurnNumber(12)
    assert public.game.outcome == "full_success"
    assert public.game.check is not None
    assert public.game.check.dice == (6, 4, 2)
    assert public.dialogues[0].speaker_id == EntityId("luna")
    assert public.visual.render_status == "not_attempted"
    assert "committed_state" not in public.model_dump(mode="json")


def test_visual_failure_is_returned_without_failing_completed_turn() -> None:
    public = TurnResultMapper.map(_internal_result(visual_issue=True))

    assert public.visual.vst_status == "failed"
    assert public.visual.render_status == "failed"
    assert public.visual.render_error == "Renderer offline"
    assert public.visual.retry_available is True
    assert public.diagnostics.memory_stored is True
    assert public.diagnostics.issues[0].code == "renderer.offline"
