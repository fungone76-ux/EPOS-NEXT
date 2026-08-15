"""Pure mapping from Module 18 internals to the stable Module 19 contract."""

from __future__ import annotations

from epos.application.conversation.models import NPCDialogueDraft
from epos.application.results.models import (
    TurnCheckResult,
    TurnDiagnostics,
    TurnDialogueLine,
    TurnGameResult,
    TurnIssue,
    TurnResult,
    TurnVisualLora,
    TurnVisualResult,
)
from epos.application.turn.models import CheckDecision, TurnOrchestrationResult


class TurnResultMapper:
    """Map once; never invokes interpretation, cognition, narration, dice, or rendering."""

    @staticmethod
    def map(result: TurnOrchestrationResult) -> TurnResult:
        return TurnResult(
            session_id=result.committed_state.session_id,
            turn_number=result.committed_state.turn_number,
            narration=result.narration.text,
            dialogues=tuple(
                TurnDialogueLine(speaker_id=unit.speaker_id, text=unit.text)
                for unit in result.narration.units
                if isinstance(unit, NPCDialogueDraft)
            ),
            game=TurnResultMapper._game(result),
            visual=TurnResultMapper._visual(result),
            diagnostics=TurnDiagnostics(
                scene_id=result.scene.scene_id,
                checkpoint_reused=result.checkpoint_reused,
                memory_stored=result.memory_stored,
                issues=tuple(
                    TurnIssue(phase=item.phase, code=item.code, message=item.message)
                    for item in result.post_commit_issues
                ),
            ),
        )

    @staticmethod
    def _game(result: TurnOrchestrationResult) -> TurnGameResult:
        if result.resolved_check is not None:
            check = result.resolved_check
            return TurnGameResult(
                outcome=check.outcome.value,
                check=TurnCheckResult(
                    skill_id=check.skill_id,
                    difficulty=check.difficulty,
                    dice=check.dice,
                    success_count=check.success_count,
                    outcome=check.outcome.value,
                ),
            )
        if result.check_decision is CheckDecision.DECLINE:
            return TurnGameResult(outcome="declined")
        return TurnGameResult(outcome="no_check")

    @staticmethod
    def _visual(result: TurnOrchestrationResult) -> TurnVisualResult:
        visual = result.visual
        if visual is None:
            issue = next(
                (item for item in result.post_commit_issues if item.phase == "visual"),
                None,
            )
            return TurnVisualResult(
                vst_status="failed" if issue is not None else "unavailable",
                render_status="failed" if issue is not None else "not_attempted",
                render_error=issue.message if issue is not None else None,
                retry_available=issue is not None,
            )

        rendered = visual.render_result
        return TurnVisualResult(
            vst_status="ok",
            positive_prompt=visual.prompt_contract.positive_prompt,
            negative_prompt=visual.prompt_contract.negative_prompt,
            loras=tuple(
                TurnVisualLora(
                    entity_id=lora.entity_id,
                    alias=lora.alias,
                    filename=lora.filename,
                )
                for lora in visual.prompt_contract.loras
            ),
            image_path=rendered.image_path,
            render_status=rendered.status,
            render_error=rendered.error,
            backend=rendered.backend,
            prompt_id=rendered.prompt_id,
            diagnostics_path=visual.diagnostics_path,
            retry_available=rendered.status == "failed",
        )
