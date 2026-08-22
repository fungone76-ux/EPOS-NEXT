"""Python-authoritative RAW VST to Canonical VST transformation."""

from __future__ import annotations

from epos.application.visual.canonical.errors import (
    SemanticLibraryResolutionError,
    VisualCanonicalizationError,
)
from epos.application.visual.canonical.library import (
    SemanticLibraryResolver,
    SemanticResolverProtocol,
)
from epos.application.visual.canonical.models import (
    CanonicalAction,
    CanonicalCamera,
    CanonicalLocation,
    CanonicalSubject,
    CanonicalVisualFocus,
    CanonicalVisualIdentity,
    CanonicalVST,
    ResolvedLora,
    ResolvedSemanticEntry,
)
from epos.application.visual.models import ObservableSceneState, ObservableSubject
from epos.application.visual.vst import RawVST, SemanticIntent, VSTSubjectIntent
from epos.application.worldpacks.models import (
    CharacterVisualCanon,
    LoadedWorldpack,
    SemanticLibraryDocument,
)
from epos.domain.ids import EntityId

_SOCIAL_ACTION_INTENTS = frozenset(
    {
        "answer",
        "ask",
        "brief_social",
        "conversation",
        "dialogue",
        "greet",
        "greeting",
        "small_talk",
        "social",
        "speak",
        "talk",
    }
)


class VisualCanonicalizer:
    """Replace LLM visual proposals with current scene and Worldpack truth."""

    def __init__(self, resolver: SemanticResolverProtocol | None = None) -> None:
        self._resolver = resolver or SemanticLibraryResolver()

    def canonicalize(
        self,
        *,
        scene: ObservableSceneState,
        raw_vst: RawVST,
        worldpack: LoadedWorldpack,
    ) -> CanonicalVST:
        self._validate_top_level(scene=scene, raw_vst=raw_vst, worldpack=worldpack)

        visible_by_id = {subject.entity_id: subject for subject in scene.visible_subjects}
        raw_by_id = {subject.entity_id: subject for subject in raw_vst.subjects}
        rendered_ids = set(raw_by_id)
        requested_focus = scene.visual_focus_candidate
        player_observation = (
            requested_focus is not None and requested_focus.reason == "player_observation"
        )
        social_turn = self._is_social_action(scene.resolved_action.action.intent)
        self._validate_subject_references(
            raw_vst=raw_vst,
            visible_ids=set(visible_by_id),
            rendered_ids=rendered_ids,
            validate_raw_focus=not player_observation,
        )
        if player_observation and requested_focus is not None:
            missing = tuple(
                subject_id
                for subject_id in requested_focus.subject_ids
                if subject_id not in rendered_ids
            )
            if missing:
                raise VisualCanonicalizationError(
                    f"player-observed subject is not rendered: {missing[0]}"
                )

        subjects = tuple(
            self._canonical_subject(
                observable=observable,
                proposed=raw_by_id[observable.entity_id],
                worldpack=worldpack,
                allow_social_action_fallback=social_turn,
            )
            for observable in scene.visible_subjects
            if observable.entity_id in rendered_ids
        )
        subject_order = tuple(subject.entity_id for subject in subjects)

        action = CanonicalAction(
            participants=self._order_ids(raw_vst.action.participants, subject_order),
            semantic=self._resolve_scene_action(
                raw_vst.action.intent,
                worldpack.action_library,
                allow_social_fallback=social_turn,
            ),
            shared=raw_vst.action.shared,
        )
        adult_action = self._authorized_adult_action(
            scene=scene,
            rendered_ids=rendered_ids,
            worldpack=worldpack,
        )
        camera_components: tuple[SemanticIntent, ...]
        if requested_focus is not None and requested_focus.reason == "player_observation":
            if requested_focus.region is None:
                raise VisualCanonicalizationError("player observation lost its body region")
            camera_components = (
                SemanticIntent(
                    description=self._observation_camera(requested_focus.region),
                    tags=("player_observation",),
                ),
            )
        else:
            camera_components = tuple(
                item
                for item in (
                    raw_vst.camera.shot,
                    raw_vst.camera.angle,
                    raw_vst.camera.composition,
                )
                if item is not None
            )
        camera = CanonicalCamera(
            semantic=self._resolver.resolve_components(
                camera_components,
                worldpack.camera_library,
                library_name="camera",
            )
        )
        if requested_focus is not None and requested_focus.reason == "player_observation":
            if requested_focus.region is None:
                raise VisualCanonicalizationError("player observation lost its body region")
            focus = CanonicalVisualFocus(
                subject_ids=self._order_ids(requested_focus.subject_ids, subject_order),
                intent=SemanticIntent(
                    description=requested_focus.region.replace("_", " "),
                    tags=("player_observation", requested_focus.region),
                ),
                region=requested_focus.region,
            )
        else:
            focus = CanonicalVisualFocus(
                subject_ids=self._order_ids(raw_vst.visual_focus.subject_ids, subject_order),
                intent=raw_vst.visual_focus.intent.model_copy(deep=True),
                region=None,
            )

        return CanonicalVST(
            scene_id=scene.scene_id,
            worldpack_id=scene.worldpack_id,
            time=scene.time.model_copy(deep=True),
            location=CanonicalLocation(
                location_id=scene.location.location_id,
                name=scene.location.name,
                environment=(
                    None
                    if raw_vst.location.environment is None
                    else raw_vst.location.environment.model_copy(deep=True)
                ),
            ),
            subjects=subjects,
            action=action,
            adult_action=adult_action,
            visual_focus=focus,
            camera=camera,
            lighting=raw_vst.lighting.model_copy(deep=True),
            style=raw_vst.style.model_copy(deep=True),
            safety=raw_vst.safety.model_copy(deep=True),
        )

    def _resolve_scene_action(
        self,
        intent: SemanticIntent,
        library: SemanticLibraryDocument,
        *,
        allow_social_fallback: bool,
    ) -> ResolvedSemanticEntry:
        if allow_social_fallback:
            return self._neutral_social_action()
        try:
            return self._resolver.resolve(intent, library, library_name="action")
        except SemanticLibraryResolutionError as exc:
            if self._is_no_match_error(exc):
                return self._neutral_social_action()
            raise

    def _resolve_optional_action(
        self,
        intent: SemanticIntent | None,
        library: SemanticLibraryDocument,
        *,
        allow_social_fallback: bool,
    ) -> ResolvedSemanticEntry | None:
        if intent is None or allow_social_fallback:
            return None
        try:
            return self._resolver.resolve(intent, library, library_name="action")
        except SemanticLibraryResolutionError as exc:
            if self._is_no_match_error(exc):
                return None
            raise

    @staticmethod
    def _is_no_match_error(error: SemanticLibraryResolutionError) -> bool:
        return str(error).startswith("no match in action library")

    @staticmethod
    def _neutral_social_action() -> ResolvedSemanticEntry:
        return ResolvedSemanticEntry(
            entry_id="no_specific_physical_action",
            description="",
            tags=("social", "neutral"),
            positive_fragment="",
        )

    @staticmethod
    def _is_social_action(intent: str) -> bool:
        return intent.strip().casefold() in _SOCIAL_ACTION_INTENTS

    def _authorized_adult_action(
        self,
        *,
        scene: ObservableSceneState,
        rendered_ids: set[EntityId],
        worldpack: LoadedWorldpack,
    ) -> ResolvedSemanticEntry | None:
        authorized = scene.authorized_intimacy_visual
        if authorized is None:
            return None
        for participant in (authorized.player_id, authorized.npc_id):
            if participant not in rendered_ids:
                raise VisualCanonicalizationError(
                    f"authorized intimacy participant is not rendered: {participant}"
                )
        library = worldpack.sex_library
        if library is None:
            raise VisualCanonicalizationError(
                "authorized intimacy requires the Worldpack sex_library"
            )
        return self._resolver.resolve(
            SemanticIntent(
                description=authorized.visual_intent,
                tags=authorized.visual_tags,
            ),
            library,
            library_name="sex",
        )

    @staticmethod
    def _observation_camera(region: str) -> str:
        if region in {"face", "head"}:
            return "close up"
        if region in {"feet", "hands", "eyes", "mouth"}:
            return "extreme close up"
        return "full body"

    @staticmethod
    def _validate_top_level(
        *,
        scene: ObservableSceneState,
        raw_vst: RawVST,
        worldpack: LoadedWorldpack,
    ) -> None:
        if raw_vst.scene_id != scene.scene_id:
            raise VisualCanonicalizationError(
                f"RAW VST scene_id does not match observable scene: {raw_vst.scene_id}"
            )
        if worldpack.world_state.worldpack_id != scene.worldpack_id:
            raise VisualCanonicalizationError(
                "visual Worldpack does not match observable scene worldpack"
            )
        if raw_vst.location.location_id != scene.location.location_id:
            raise VisualCanonicalizationError(
                "RAW VST location contradicts observable scene: "
                f"{raw_vst.location.location_id} != {scene.location.location_id}"
            )

    @staticmethod
    def _validate_subject_references(
        *,
        raw_vst: RawVST,
        visible_ids: set[EntityId],
        rendered_ids: set[EntityId],
        validate_raw_focus: bool = True,
    ) -> None:
        for subject in raw_vst.subjects:
            if subject.entity_id not in visible_ids:
                raise VisualCanonicalizationError(
                    f"RAW VST subject is not visible in canonical scene: {subject.entity_id}"
                )

        for participant in raw_vst.action.participants:
            if participant not in visible_ids:
                raise VisualCanonicalizationError(
                    f"RAW VST action participant is not visible: {participant}"
                )
            if participant not in rendered_ids:
                raise VisualCanonicalizationError(
                    f"RAW VST action participant is not rendered: {participant}"
                )

        if validate_raw_focus:
            for subject_id in raw_vst.visual_focus.subject_ids:
                if subject_id not in visible_ids:
                    raise VisualCanonicalizationError(
                        f"RAW VST visual focus target is not visible: {subject_id}"
                    )
                if subject_id not in rendered_ids:
                    raise VisualCanonicalizationError(
                        f"RAW VST visual focus target is not rendered: {subject_id}"
                    )

        if not rendered_ids:
            raise VisualCanonicalizationError("RAW VST must render at least one visible subject")

    def _canonical_subject(
        self,
        *,
        observable: ObservableSubject,
        proposed: VSTSubjectIntent,
        worldpack: LoadedWorldpack,
        allow_social_action_fallback: bool,
    ) -> CanonicalSubject:
        visual = worldpack.visual.characters.get(observable.entity_id)
        if visual is None:
            raise VisualCanonicalizationError(
                f"missing visual canon for rendered subject: {observable.entity_id}"
            )

        return CanonicalSubject(
            entity_id=observable.entity_id,
            kind=observable.kind,
            name=observable.name,
            role=observable.role,
            prominence=proposed.prominence,
            identity=self._identity(visual),
            outfit=observable.outfit.model_copy(deep=True),
            visual_state=observable.visual_state.model_copy(deep=True),
            position=observable.position,
            pose=self._resolve_optional(
                proposed.pose,
                worldpack.pose_library,
                library_name="pose",
            ),
            action=self._resolve_optional_action(
                proposed.action,
                worldpack.action_library,
                allow_social_fallback=allow_social_action_fallback,
            ),
            body_orientation=self._resolve_optional(
                proposed.body_orientation,
                worldpack.pose_library,
                library_name="pose",
            ),
            lora=self._resolve_lora(
                entity_id=observable.entity_id,
                visual=visual,
                worldpack=worldpack,
            ),
        )

    def _resolve_optional(
        self,
        intent: SemanticIntent | None,
        library: SemanticLibraryDocument,
        *,
        library_name: str,
    ) -> ResolvedSemanticEntry | None:
        if intent is None:
            return None
        return self._resolver.resolve(intent, library, library_name=library_name)

    @staticmethod
    def _identity(visual: CharacterVisualCanon) -> CanonicalVisualIdentity:
        return CanonicalVisualIdentity(
            base_prompt=visual.base_prompt,
            role_prompt=visual.role_prompt,
            visual_gender=visual.visual_gender,
            canonical_traits=visual.canonical_traits,
        )

    @staticmethod
    def _resolve_lora(
        *,
        entity_id: EntityId,
        visual: CharacterVisualCanon,
        worldpack: LoadedWorldpack,
    ) -> ResolvedLora | None:
        alias = visual.lora_alias
        if alias is None:
            return None
        filename = worldpack.visual.loras.get(alias)
        if filename is None or not filename.strip():
            raise VisualCanonicalizationError(
                f"unknown LoRA alias for {entity_id}: {alias}"
            )
        return ResolvedLora(
            entity_id=entity_id,
            alias=alias,
            filename=filename,
        )

    @staticmethod
    def _order_ids(
        ids: tuple[EntityId, ...],
        subject_order: tuple[EntityId, ...],
    ) -> tuple[EntityId, ...]:
        requested = set(ids)
        return tuple(subject_id for subject_id in subject_order if subject_id in requested)