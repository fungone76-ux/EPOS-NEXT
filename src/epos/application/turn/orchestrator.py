"""Canonical EPOS turn coordinator. Python authorizes; subsystems remain injected."""

from __future__ import annotations

import asyncio

from epos.application.actions.models import ActionInterpreterContext, ResolvedCheck, ValidatedAction
from epos.application.cognition.models import CognitionResult, CognitionScene
from epos.application.state import (
    AdvanceTurnMutation,
    AuthoritativeStateManager,
    DiceCheckpoint,
    DiceCheckpointService,
    MutationAuthority,
    MutationBatch,
)
from epos.application.turn.errors import (
    CheckDecisionRequiredError,
    PendingDiceCheckpointError,
    TurnCommitMismatchError,
    TurnOrchestrationError,
)
from epos.application.turn.models import (
    CheckDecision,
    PostCommitIssue,
    TurnCommand,
    TurnMemoryContext,
    TurnOrchestrationResult,
)
from epos.application.turn.ports import (
    ReactionMutationPlannerPort,
    TurnActionInterpreterPort,
    TurnActionResolverPort,
    TurnCheckResolverPort,
    TurnCognitionPort,
    TurnMemoryPort,
    TurnNarrationPort,
    TurnPsychologyPort,
    TurnScenePort,
    TurnVisualPort,
)
from epos.application.visual.models import SubjectKind
from epos.domain.errors import EposError
from epos.domain.ids import EntityId
from epos.domain.world_state import WorldState


class TurnOrchestrator:
    """Coordinate exactly one authoritative turn without implementing its subsystems."""

    def __init__(
        self,
        *,
        state: AuthoritativeStateManager,
        checkpoint: DiceCheckpointService,
        interpreter: TurnActionInterpreterPort,
        check_resolver: TurnCheckResolverPort,
        action_resolver: TurnActionResolverPort,
        psychology: TurnPsychologyPort,
        cognition: TurnCognitionPort,
        reaction_mutations: ReactionMutationPlannerPort,
        scene_builder: TurnScenePort,
        narration: TurnNarrationPort,
        visual: TurnVisualPort,
        memory: TurnMemoryPort,
    ) -> None:
        self._state = state
        self._checkpoint = checkpoint
        self._interpreter = interpreter
        self._check_resolver = check_resolver
        self._action_resolver = action_resolver
        self._psychology = psychology
        self._cognition = cognition
        self._reaction_mutations = reaction_mutations
        self._scene_builder = scene_builder
        self._narration = narration
        self._visual = visual
        self._memory = memory
        self._turn_lock = asyncio.Lock()

    async def run(self, command: TurnCommand) -> TurnOrchestrationResult:
        async with self._turn_lock:
            return await self._run_locked(command)

    async def _run_locked(self, command: TurnCommand) -> TurnOrchestrationResult:
        pre_state = self._state.snapshot()
        checkpoint = await self._checkpoint.resume(state=pre_state)
        action, decision, resolved_check, reused = await self._resolve_input_and_check(
            command=command,
            state=pre_state,
            checkpoint=checkpoint,
        )

        action_resolution = self._action_resolver.resolve(
            state=pre_state,
            action=action,
            check_decision=decision,
            resolved_check=resolved_check,
        )
        action_state = self._state.project_many(
            action_resolution.mutation_batches,
            base_state=pre_state,
        )
        present_after_action = self._present_npc_ids(action_state)

        psychology_plan = self._psychology.plan(
            state=action_state,
            action=action,
            resolved_check=resolved_check,
            present_npc_ids=present_after_action,
        )
        psychological_state = self._state.project_many(
            action_resolution.mutation_batches + psychology_plan.mutation_batches,
            base_state=pre_state,
        )
        present_npc_ids = self._present_npc_ids(psychological_state)

        cognition_scene = self._cognition_scene(
            psychological_state,
            action_resolution.observable_consequences,
        )
        cognition_results = await self._process_present_npcs(
            state=psychological_state,
            npc_ids=present_npc_ids,
            scene=cognition_scene,
            player_input=command.player_input,
            action=action,
            resolved_check=resolved_check,
        )
        reaction_batch = self._reaction_mutations.plan(cognition_results)
        advance_batch = MutationBatch(
            producer=MutationAuthority.ENGINE_ONLY,
            mutations=(AdvanceTurnMutation(),),
        )
        all_batches = (
            action_resolution.mutation_batches
            + psychology_plan.mutation_batches
            + (reaction_batch, advance_batch)
        )
        projected_final = self._state.project_many(all_batches, base_state=pre_state)

        scene = self._scene_builder.build(
            state=projected_final,
            action=action,
            resolved_check=resolved_check,
            resolution=action_resolution,
        )
        narration = await self._narration.generate(
            state=projected_final,
            scene=scene,
            player_input=command.player_input,
            action=action,
            reactions=cognition_results,
        )

        committed = await self._state.commit_many(
            all_batches,
            expected_state=pre_state,
        )
        if committed != projected_final:
            raise TurnCommitMismatchError(
                "committed authoritative state differs from validated turn projection"
            )

        issues: list[PostCommitIssue] = []
        if checkpoint is not None or (action.check is not None and decision is CheckDecision.ROLL):
            try:
                await self._checkpoint.clear(state=committed)
            except EposError as exc:
                issues.append(self._issue("checkpoint_clear", exc))

        visual_result = None
        try:
            visual_result = await self._visual.render(scene)
        except EposError as exc:
            issues.append(self._issue("visual", exc))

        memory_stored = False
        try:
            await self._memory.remember(
                TurnMemoryContext(
                    committed_state=committed,
                    player_input=command.player_input,
                    action=action,
                    resolved_check=resolved_check,
                    reactions=tuple(result.reaction for result in cognition_results),
                    scene=scene,
                    narration=narration,
                )
            )
            memory_stored = True
        except EposError as exc:
            issues.append(self._issue("memory", exc))

        return TurnOrchestrationResult(
            committed_state=committed,
            action=action,
            check_decision=decision,
            resolved_check=resolved_check,
            checkpoint_reused=reused,
            cognition_results=cognition_results,
            scene=scene,
            narration=narration,
            visual=visual_result,
            memory_stored=memory_stored,
            post_commit_issues=tuple(issues),
        )

    async def _resolve_input_and_check(
        self,
        *,
        command: TurnCommand,
        state: WorldState,
        checkpoint: DiceCheckpoint | None,
    ) -> tuple[ValidatedAction, CheckDecision | None, ResolvedCheck | None, bool]:
        if checkpoint is not None:
            if checkpoint.player_input != command.player_input:
                raise PendingDiceCheckpointError(
                    "a crashed dice turn is pending; new player input cannot replace it"
                )
            try:
                decision = CheckDecision(checkpoint.player_decision)
            except ValueError as exc:
                raise PendingDiceCheckpointError(
                    "pending dice checkpoint contains an unsupported player decision"
                ) from exc
            return (
                checkpoint.validated_action.model_copy(deep=True),
                decision,
                checkpoint.resolved_check.model_copy(deep=True),
                True,
            )

        context = ActionInterpreterContext.from_world_state(
            state,
            player_input=command.player_input,
            known_location_ids=command.known_location_ids,
        )
        action = await self._interpreter.interpret(context)
        if action.check is None:
            return action, None, None, False

        if command.check_decision is None:
            raise CheckDecisionRequiredError()
        if command.check_decision is CheckDecision.DECLINE:
            return action, CheckDecision.DECLINE, None, False

        rating = action.skill_rating
        if rating is None:
            raise TurnOrchestrationError(
                "validated checked action has no authoritative skill rating",
                code="turn.check_missing_rating",
            )
        resolved = self._check_resolver.resolve(action.check, rating=rating)
        await self._checkpoint.save_after_roll(
            state=state,
            player_input=command.player_input,
            validated_action=action,
            proposal=action.check,
            resolved_check=resolved,
            player_decision=CheckDecision.ROLL.value,
        )
        return action, CheckDecision.ROLL, resolved, False

    async def _process_present_npcs(
        self,
        *,
        state: WorldState,
        npc_ids: tuple[EntityId, ...],
        scene: CognitionScene,
        player_input: str,
        action: ValidatedAction,
        resolved_check: ResolvedCheck | None,
    ) -> tuple[CognitionResult, ...]:
        results: list[CognitionResult] = []
        for npc_id in npc_ids:
            result = await self._cognition.react(
                state=state,
                npc_id=npc_id,
                scene=scene,
                player_input=player_input,
                action=action,
                resolved_check=resolved_check,
            )
            if result is not None:
                results.append(result)
        return tuple(results)

    @staticmethod
    def _present_npc_ids(state: WorldState) -> tuple[EntityId, ...]:
        return tuple(
            sorted(
                (
                    npc_id
                    for npc_id, npc in state.npcs.items()
                    if npc.location_id == state.player.location_id
                ),
                key=str,
            )
        )

    @staticmethod
    def _cognition_scene(
        state: WorldState,
        consequences: tuple[object, ...],
    ) -> CognitionScene:
        facts = tuple(
            consequence.fact
            for consequence in consequences
            if hasattr(consequence, "fact") and isinstance(consequence.fact, str)
        )
        present = (state.player.entity_id, *TurnOrchestrator._present_npc_ids(state))
        return CognitionScene(
            location_id=state.player.location_id,
            present_entity_ids=present,
            observable_facts=facts,
            summary=f"turn {int(state.turn_number)} at {state.player.location_id}",
        )

    @staticmethod
    def _issue(phase: str, exc: EposError) -> PostCommitIssue:
        return PostCommitIssue(phase=phase, code=exc.code, message=str(exc))
