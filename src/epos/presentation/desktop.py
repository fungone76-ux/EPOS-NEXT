"""Desktop presentation for EPOS NEXT.

The Qt shell deliberately mirrors the original EPOS three-panel game UI:
State | Scene | Story. The controller remains framework-independent and all
slow runtime calls are executed away from Qt's main thread.
"""

from __future__ import annotations

import asyncio
import html
import importlib
import threading
from collections.abc import Callable
from pathlib import Path
from typing import Any, cast

from epos.application.turn import TurnCommand
from epos.domain.errors import ConfigurationError
from epos.domain.ids import EntityId, SessionId
from epos.presentation.models import (
    DesktopViewState,
    SessionView,
    StoryPanelState,
    VisualPanelState,
)
from epos.presentation.ports import EPOSRuntimePort

_OUTCOME_LABELS = {
    "no_check": "AZIONE NARRATIVA",
    "declined": "AZIONE NON ESEGUITA",
    "critical_failure": "FALLIMENTO CRITICO",
    "failure": "FALLIMENTO",
    "partial_success": "SUCCESSO PARZIALE",
    "full_success": "SUCCESSO PIENO",
}


_STYLESHEET = """
QMainWindow, QWidget {
    background: #16181d;
    color: #eceff4;
    font-family: "Segoe UI";
    font-size: 15px;
}
QFrame#panel {
    background: #20232a;
    border: 1px solid #343944;
    border-radius: 10px;
}
QLabel#panelTitle { font-size: 20px; font-weight: 700; padding: 4px; }
QLabel#stateText { padding: 2px; }
QFrame#narrationCard {
    background: #252932;
    border-left: 4px solid #8f9bb3;
    border-radius: 8px;
}
QFrame#dialogueBubble {
    background: #2a303a;
    border: 1px solid #414958;
    border-radius: 12px;
}
QFrame#playerBubble {
    background: #233024;
    border: 1px solid #3c5340;
    border-radius: 12px;
}
QLabel#speakerName { font-weight: 800; font-size: 16px; color: #f1c27d; }
QLabel#systemLine { color: #aeb6c5; font-style: italic; padding: 4px; }
QLabel#outcomeFull { color: #7fc97f; font-weight: 800; padding: 3px 6px; }
QLabel#outcomePartial { color: #e6c07a; font-weight: 800; padding: 3px 6px; }
QLabel#outcomeFail { color: #e07a7a; font-weight: 800; padding: 3px 6px; }
QTextEdit {
    background: #111318;
    border: 1px solid #3a404d;
    border-radius: 8px;
    padding: 10px;
}
QPushButton {
    background: #3b6ea8;
    border: 0;
    border-radius: 8px;
    padding: 10px 16px;
    font-weight: 700;
}
QPushButton:hover { background: #4780bd; }
QPushButton:disabled { background: #343841; color: #777777; }
QPushButton#secondary { background: #343944; }
QPushButton#secondary:hover { background: #414958; }
QScrollArea { border: 0; }
QCheckBox { padding: 3px; }
QStatusBar { background: #101216; color: #9aa7bd; }
QSplitter::handle { background: #16181d; width: 5px; }
QScrollBar:vertical { background: #17191f; width: 11px; margin: 0; }
QScrollBar::handle:vertical { background: #414958; border-radius: 5px; min-height: 28px; }
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
"""


def _escaped(value: object) -> str:
    return html.escape(str(value))


def _state_section(title: str, lines: list[str]) -> str:
    if not lines:
        lines = ["—"]
    body = "<br>".join(lines)
    return f'<p><span style="color:#f1c27d;font-weight:700">{title}</span><br>{body}</p>'


def session_state_html(session: SessionView) -> str:
    """Return the readable state card used by the GUI, never raw state JSON."""

    player = session.player
    sections = [
        _state_section(
            "SITUAZIONE",
            [
                f"<b>{_escaped(session.location_name)}</b>",
                f"Giorno {session.day} · {_escaped(session.world_phase)}",
                f"Turno {int(session.turn_number)}",
            ],
        )
    ]
    if player is not None:
        player_lines = [f"<b>{_escaped(player.name)}</b>"]
        player_lines.append(
            "Outfit: " + (", ".join(_escaped(item) for item in player.outfit) or "nessuno")
        )
        if player.conditions:
            player_lines.append(
                "Condizioni: " + ", ".join(_escaped(item) for item in player.conditions)
            )
        if player.inventory:
            player_lines.append(
                "Inventario: " + ", ".join(_escaped(item) for item in player.inventory)
            )
        sections.append(_state_section("PERSONAGGIO", player_lines))

    skill_lines = []
    for skill in session.player_skills:
        rating = "—" if skill.rating is None else f"{skill.rating:g}"
        skill_lines.append(f"{_escaped(skill.name)}: <b>{rating}</b>")
    sections.append(_state_section("ABILITÀ", skill_lines))

    npc_lines = []
    for npc in session.present_npcs:
        outfit = ", ".join(_escaped(item) for item in npc.outfit)
        suffix = f"<br><span style='color:#9aa7bd'>Outfit: {outfit}</span>" if outfit else ""
        npc_lines.append(f"<b>{_escaped(npc.name)}</b> · {_escaped(npc.role)}{suffix}")
    sections.append(_state_section("NPC PRESENTI", npc_lines))

    mission_lines = [
        f"{_escaped(mission.mission_id)} · {_escaped(mission.status)}"
        for mission in session.missions
    ]
    thread_lines = [
        f"{_escaped(thread.thread_id)} · {_escaped(thread.status)}" for thread in session.threads
    ]
    sections.append(_state_section("MISSIONI E THREAD", mission_lines + thread_lines))

    event_lines = [
        f"{_escaped(event.event_id)} · {_escaped(event.status)}" for event in session.events
    ]
    sections.append(_state_section("EVENTI", event_lines))
    return "".join(sections)


def visual_debug_text(visual: VisualPanelState) -> str:
    result = visual.result
    if result is None:
        return "Nessun contratto visuale disponibile per questa sessione."
    lines = [
        f"VST: {result.vst_status}",
        f"Render: {result.render_status}",
    ]
    if result.backend:
        lines.append(f"Backend: {result.backend}")
    if result.prompt_id:
        lines.append(f"Prompt ID: {result.prompt_id}")
    if result.loras:
        lines.append("LoRA: " + ", ".join(item.alias for item in result.loras))
    if result.positive_prompt:
        lines.extend(("", "PROMPT POSITIVO", result.positive_prompt))
    if result.negative_prompt:
        lines.extend(("", "PROMPT NEGATIVO", result.negative_prompt))
    if result.render_error:
        lines.extend(("", "ERRORE", result.render_error))
    if result.diagnostics_path:
        lines.extend(("", f"Diagnostica: {result.diagnostics_path}"))
    return "\n".join(lines)


class DesktopController:
    def __init__(self, runtime: EPOSRuntimePort) -> None:
        self._runtime = runtime
        self._state: DesktopViewState | None = None

    @property
    def state(self) -> DesktopViewState:
        if self._state is None:
            raise RuntimeError("desktop controller is not initialized")
        return self._state.model_copy(deep=True)

    async def initialize(self, session_id: SessionId) -> DesktopViewState:
        session, health = await asyncio.gather(
            self._runtime.get_session(session_id),
            self._runtime.health(),
        )
        self._state = DesktopViewState(session=session, health=health)
        return self.state

    async def submit_player_input(self, player_input: str) -> DesktopViewState:
        current = self.state
        result = await self._runtime.run_turn(
            current.session.session_id,
            TurnCommand(player_input=player_input),
        )
        session = await self._runtime.get_session(current.session.session_id)
        health = await self._runtime.health()
        self._state = DesktopViewState(
            session=session,
            story=StoryPanelState(
                narration=result.narration,
                dialogues=result.dialogues,
                game=result.game,
            ),
            visual=VisualPanelState(
                current_image=result.visual.image_path,
                result=result.visual,
                show_debug=current.visual.show_debug,
            ),
            health=health,
        )
        return self.state

    async def retry_image(self) -> DesktopViewState:
        current = self.state
        visual = await self._runtime.rerender(current.session.session_id)
        self._state = current.model_copy(
            update={
                "visual": VisualPanelState(
                    current_image=visual.image_path,
                    result=visual,
                    show_debug=current.visual.show_debug,
                )
            },
            deep=True,
        )
        return self.state

    async def new_session(self) -> DesktopViewState:
        current = self.state
        session = await self._runtime.create_session(current.session.worldpack_id)
        health = await self._runtime.health()
        self._state = DesktopViewState(
            session=session,
            visual=VisualPanelState(show_debug=current.visual.show_debug),
            health=health,
        )
        return self.state

    async def resume_session(self) -> DesktopViewState:
        current = self.state
        session = await self._runtime.resume(current.session.session_id)
        health = await self._runtime.health()
        self._state = current.model_copy(update={"session": session, "health": health}, deep=True)
        return self.state

    def set_visual_debug(self, enabled: bool) -> DesktopViewState:
        current = self.state
        self._state = current.model_copy(
            update={"visual": current.visual.model_copy(update={"show_debug": enabled})},
            deep=True,
        )
        return self.state


class QtDesktopLauncher:
    """Qt adapter for the original EPOS-style three-panel layout."""

    def __init__(self, controller: DesktopController, session_id: SessionId) -> None:
        self._controller = controller
        self._session_id = session_id

    def run(self) -> int:
        try:
            qt_core = importlib.import_module("PySide6.QtCore")
            qt_gui = importlib.import_module("PySide6.QtGui")
            qt_widgets = importlib.import_module("PySide6.QtWidgets")
        except ModuleNotFoundError as exc:
            raise ConfigurationError(
                "PySide6 is required for the desktop GUI; install epos-next[gui]"
            ) from exc

        view = asyncio.run(self._controller.initialize(self._session_id))
        app = qt_widgets.QApplication.instance() or qt_widgets.QApplication([])

        class SubmitTextEdit(qt_widgets.QTextEdit):  # type: ignore[name-defined,misc]
            submit_requested = qt_core.Signal()

            def keyPressEvent(self, event: Any) -> None:
                if event.key() in (qt_core.Qt.Key_Return, qt_core.Qt.Key_Enter) and not (
                    event.modifiers() & qt_core.Qt.ShiftModifier
                ):
                    event.accept()
                    self.submit_requested.emit()
                    return
                super().keyPressEvent(event)

        class ImagePreviewLabel(qt_widgets.QLabel):  # type: ignore[name-defined,misc]
            clicked = qt_core.Signal()

            def __init__(self, text: str) -> None:
                super().__init__(text)
                self._source = qt_gui.QPixmap()
                self.source_path: Path | None = None

            def show_path(self, image_path: str) -> bool:
                pixmap = qt_gui.QPixmap(image_path)
                if pixmap.isNull():
                    self._source = qt_gui.QPixmap()
                    self.source_path = None
                    self.setText(f"Immagine non leggibile\n{image_path}")
                    return False
                self._source = pixmap
                self.source_path = Path(image_path)
                self._fit()
                self.setCursor(qt_core.Qt.PointingHandCursor)
                self.setToolTip("Clicca per aprire l'immagine con zoom e pan")
                return True

            def clear_image(self) -> None:
                self._source = qt_gui.QPixmap()
                self.source_path = None
                self.clear()
                self.setText("Immagine non ancora generata")

            def _fit(self) -> None:
                if not self._source.isNull():
                    self.setPixmap(
                        self._source.scaled(
                            self.size(),
                            qt_core.Qt.KeepAspectRatio,
                            qt_core.Qt.SmoothTransformation,
                        )
                    )

            def resizeEvent(self, event: Any) -> None:
                super().resizeEvent(event)
                self._fit()

            def mousePressEvent(self, event: Any) -> None:
                if event.button() == qt_core.Qt.LeftButton and not self._source.isNull():
                    self.clicked.emit()
                    event.accept()
                    return
                super().mousePressEvent(event)

        class ZoomableView(qt_widgets.QGraphicsView):  # type: ignore[name-defined,misc]
            def __init__(self, scene: Any) -> None:
                super().__init__(scene)
                self.setDragMode(qt_widgets.QGraphicsView.ScrollHandDrag)
                self.setTransformationAnchor(qt_widgets.QGraphicsView.AnchorUnderMouse)
                self.setResizeAnchor(qt_widgets.QGraphicsView.AnchorViewCenter)
                self.setBackgroundBrush(qt_core.Qt.black)

            def wheelEvent(self, event: Any) -> None:
                factor = 1.25 if event.angleDelta().y() > 0 else 0.8
                self.scale(factor, factor)
                event.accept()

        class ImageViewer(qt_widgets.QDialog):  # type: ignore[name-defined,misc]
            def __init__(self, image_path: Path, parent: Any) -> None:
                super().__init__(parent)
                self.setWindowTitle(image_path.name)
                self.resize(1100, 800)
                box = qt_widgets.QVBoxLayout(self)
                scene = qt_widgets.QGraphicsScene(self)
                self.item = qt_widgets.QGraphicsPixmapItem(qt_gui.QPixmap(str(image_path)))
                scene.addItem(self.item)
                self.graphics = ZoomableView(scene)
                box.addWidget(self.graphics)
                hint = qt_widgets.QLabel(
                    "Rotellina: zoom  •  Trascina: pan  •  Doppio clic: adatta"
                )
                hint.setAlignment(qt_core.Qt.AlignCenter)
                box.addWidget(hint)
                qt_core.QTimer.singleShot(0, self.fit_image)

            def fit_image(self) -> None:
                self.graphics.fitInView(self.item, qt_core.Qt.KeepAspectRatio)

            def mouseDoubleClickEvent(self, event: Any) -> None:
                self.fit_image()
                super().mouseDoubleClickEvent(event)

        class WorkerBridge(qt_core.QObject):  # type: ignore[name-defined,misc]
            completed = qt_core.Signal(object)

        window = qt_widgets.QMainWindow()
        window.setWindowTitle(f"EPOS NEXT — {view.session.worldpack_id}")
        window.resize(1400, 820)
        window.setMinimumSize(980, 700)
        window.setStyleSheet(_STYLESHEET)
        bridge = WorkerBridge(window)
        image_viewers: list[Any] = []
        busy = {"value": False}

        def panel(title: str) -> tuple[Any, Any]:
            frame = qt_widgets.QFrame()
            frame.setObjectName("panel")
            box = qt_widgets.QVBoxLayout(frame)
            box.setContentsMargins(14, 14, 14, 14)
            heading = qt_widgets.QLabel(title)
            heading.setObjectName("panelTitle")
            box.addWidget(heading)
            return frame, box

        splitter = qt_widgets.QSplitter(qt_core.Qt.Horizontal)
        splitter.setChildrenCollapsible(False)

        state_panel, state_box = panel("Stato")
        state_scroll = qt_widgets.QScrollArea()
        state_scroll.setWidgetResizable(True)
        state_scroll.setHorizontalScrollBarPolicy(qt_core.Qt.ScrollBarAlwaysOff)
        state_holder = qt_widgets.QWidget()
        state_layout = qt_widgets.QVBoxLayout(state_holder)
        state_layout.setContentsMargins(0, 0, 0, 0)
        state_label = qt_widgets.QLabel()
        state_label.setObjectName("stateText")
        state_label.setWordWrap(True)
        state_label.setTextInteractionFlags(qt_core.Qt.TextSelectableByMouse)
        state_label.setAlignment(qt_core.Qt.AlignTop)
        state_layout.addWidget(state_label)
        state_layout.addStretch(1)
        state_scroll.setWidget(state_holder)
        state_box.addWidget(state_scroll, 1)
        session_buttons = qt_widgets.QHBoxLayout()
        new_button = qt_widgets.QPushButton("Nuova")
        new_button.setObjectName("secondary")
        reload_button = qt_widgets.QPushButton("Ricarica")
        reload_button.setObjectName("secondary")
        session_buttons.addWidget(new_button)
        session_buttons.addWidget(reload_button)
        state_box.addLayout(session_buttons)
        autosave = qt_widgets.QLabel("Salvataggio automatico dopo ogni turno")
        autosave.setObjectName("systemLine")
        autosave.setAlignment(qt_core.Qt.AlignCenter)
        state_box.addWidget(autosave)

        visual_panel, visual_box = panel("Scena")
        image_label = ImagePreviewLabel("Immagine non ancora generata")
        image_label.setAlignment(qt_core.Qt.AlignCenter)
        image_label.setMinimumSize(360, 360)
        image_label.setSizePolicy(
            qt_widgets.QSizePolicy.Ignored,
            qt_widgets.QSizePolicy.Ignored,
        )
        image_label.setStyleSheet(
            "background:#0d0f13;border:1px solid #3a404d;border-radius:8px;"
        )
        visual_box.addWidget(image_label, 3)
        visual_buttons = qt_widgets.QHBoxLayout()
        retry_button = qt_widgets.QPushButton("Rerender")
        retry_button.setObjectName("secondary")
        debug_toggle = qt_widgets.QPushButton("Mostra prompt visuale")
        debug_toggle.setObjectName("secondary")
        visual_buttons.addWidget(retry_button)
        visual_buttons.addWidget(debug_toggle)
        visual_box.addLayout(visual_buttons)
        debug_text = qt_widgets.QTextEdit()
        debug_text.setReadOnly(True)
        debug_text.setVisible(False)
        debug_text.setMinimumHeight(150)
        visual_box.addWidget(debug_text, 2)

        story_panel, story_box = panel("Storia")
        story_scroll = qt_widgets.QScrollArea()
        story_scroll.setWidgetResizable(True)
        story_container = qt_widgets.QWidget()
        story_layout = qt_widgets.QVBoxLayout(story_container)
        story_layout.setAlignment(qt_core.Qt.AlignTop)
        story_layout.setSpacing(10)
        story_scroll.setWidget(story_container)
        story_box.addWidget(story_scroll, 1)
        phase_label = qt_widgets.QLabel("Fase: pronta")
        phase_label.setObjectName("systemLine")
        story_box.addWidget(phase_label)
        player_input = SubmitTextEdit()
        player_input.setPlaceholderText(
            "Scrivi liberamente ciò che fai o dici… "
            "(Invio per inviare, Maiusc+Invio per andare a capo)"
        )
        player_input.setMaximumHeight(95)
        story_box.addWidget(player_input)
        send_button = qt_widgets.QPushButton("Invia")
        story_box.addWidget(send_button)

        splitter.addWidget(state_panel)
        splitter.addWidget(visual_panel)
        splitter.addWidget(story_panel)
        splitter.setSizes([300, 520, 580])
        window.setCentralWidget(splitter)
        status = window.statusBar()

        action_widgets = (
            new_button,
            reload_button,
            retry_button,
            send_button,
            player_input,
        )

        def scroll_story() -> None:
            qt_core.QTimer.singleShot(
                0,
                lambda: story_scroll.verticalScrollBar().setValue(
                    story_scroll.verticalScrollBar().maximum()
                ),
            )

        def narration_card(text: str) -> None:
            if not text.strip():
                return
            card = qt_widgets.QFrame()
            card.setObjectName("narrationCard")
            box = qt_widgets.QVBoxLayout(card)
            box.setContentsMargins(14, 12, 14, 12)
            label = qt_widgets.QLabel(text.strip())
            label.setWordWrap(True)
            label.setTextInteractionFlags(qt_core.Qt.TextSelectableByMouse)
            box.addWidget(label)
            story_layout.addWidget(card)
            scroll_story()

        def dialogue_bubble(speaker: str, text: str, *, player: bool = False) -> None:
            card = qt_widgets.QFrame()
            card.setObjectName("playerBubble" if player else "dialogueBubble")
            box = qt_widgets.QVBoxLayout(card)
            box.setContentsMargins(14, 10, 14, 12)
            box.setSpacing(5)
            name = qt_widgets.QLabel(speaker)
            name.setObjectName("speakerName")
            box.addWidget(name)
            body = qt_widgets.QLabel(text)
            body.setWordWrap(True)
            body.setTextInteractionFlags(qt_core.Qt.TextSelectableByMouse)
            box.addWidget(body)
            story_layout.addWidget(card)
            scroll_story()

        def system_line(text: str, object_name: str = "systemLine") -> None:
            label = qt_widgets.QLabel(text)
            label.setObjectName(object_name)
            label.setWordWrap(True)
            story_layout.addWidget(label)
            scroll_story()

        def clear_story() -> None:
            while story_layout.count():
                item = story_layout.takeAt(0)
                widget = item.widget()
                if widget is not None:
                    widget.deleteLater()

        def speaker_name(session: SessionView, speaker_id: EntityId) -> str:
            if session.player is not None and speaker_id == session.player.entity_id:
                return session.player.name
            for npc in session.present_npcs:
                if npc.entity_id == speaker_id:
                    return npc.name
            return str(speaker_id)

        def health_line(current: DesktopViewState) -> str:
            return (
                f"LLM {current.health.llm.status}  •  "
                f"Renderer {current.health.renderer.status}  •  "
                f"Sessione {current.session.session_id}"
            )

        def refresh(current: DesktopViewState) -> None:
            state_label.setText(session_state_html(current.session))
            debug_text.setPlainText(visual_debug_text(current.visual))
            debug_text.setVisible(current.visual.show_debug)
            debug_toggle.setText(
                "Nascondi prompt visuale"
                if current.visual.show_debug
                else "Mostra prompt visuale"
            )
            visual = current.visual.result
            retry_button.setEnabled(
                not busy["value"] and bool(visual and visual.retry_available)
            )
            if current.visual.current_image:
                image_label.show_path(current.visual.current_image)
            elif visual is None:
                image_label.clear_image()
            elif visual.render_status == "failed":
                image_label.clear_image()
                image_label.setText("Rendering fallito\nUsa Rerender per riprovare")
            status.showMessage(health_line(current))
            window.setWindowTitle(
                f"EPOS NEXT — {current.session.worldpack_id} — "
                f"{str(current.session.session_id)[:18]}"
            )

        def set_busy(enabled: bool, message: str) -> None:
            busy["value"] = enabled
            for widget in action_widgets:
                widget.setEnabled(not enabled)
            if not enabled:
                current_visual = self._controller.state.visual.result
                retry_button.setEnabled(bool(current_visual and current_visual.retry_available))
            phase_label.setText(f"Fase: {message}")
            status.showMessage(message)
            if enabled:
                app.setOverrideCursor(qt_core.Qt.WaitCursor)
            else:
                app.restoreOverrideCursor()

        def operation_finished(payload: tuple[str, object, object]) -> None:
            kind, value, callback = payload
            if kind == "ok":
                cast(Callable[[object], None], callback)(value)
                set_busy(False, "pronta")
                player_input.setFocus()
                return
            set_busy(False, "errore")
            system_line(f"[operazione non completata: {value}]")
            status.showMessage(f"Errore: {value}")

        bridge.completed.connect(operation_finished, qt_core.Qt.QueuedConnection)

        def run_async(
            operation: Callable[[], Any],
            callback: Callable[[DesktopViewState], None],
            message: str,
        ) -> None:
            if busy["value"]:
                return
            set_busy(True, message)

            def worker() -> None:
                try:
                    result = asyncio.run(operation())
                except Exception as exc:  # reported without losing committed state
                    bridge.completed.emit(("error", exc, callback))
                else:
                    bridge.completed.emit(("ok", result, callback))

            threading.Thread(target=worker, daemon=True).start()

        def present_turn(current: DesktopViewState) -> None:
            game = current.story.game
            if game is not None and game.check is not None:
                dice = "  ".join(str(value) for value in game.check.dice)
                system_line(f"🎲  {dice}")
            if game is not None and game.outcome != "no_check":
                style = "outcomeFull"
                if game.outcome == "partial_success":
                    style = "outcomePartial"
                elif game.outcome in {"failure", "critical_failure", "declined"}:
                    style = "outcomeFail"
                system_line(_OUTCOME_LABELS[game.outcome], style)
            narration_card(current.story.narration)
            for line in current.story.dialogues:
                dialogue_bubble(
                    speaker_name(current.session, line.speaker_id),
                    f"«{line.text}»",
                )
            if (
                current.visual.result is not None
                and current.visual.result.render_status == "failed"
            ):
                system_line(
                    "[rendering fallito: "
                    f"{current.visual.result.render_error or 'errore sconosciuto'} — "
                    "usa Rerender per riprovare]"
                )
            refresh(current)

        def submit() -> None:
            text = player_input.toPlainText().strip()
            if not text or busy["value"]:
                return
            player_input.clear()
            current = self._controller.state
            name = current.session.player.name if current.session.player is not None else "Tu"
            dialogue_bubble(name, text, player=True)
            run_async(
                lambda: self._controller.submit_player_input(text),
                present_turn,
                "il Game Master sta pensando…",
            )

        def retry() -> None:
            def presented(current: DesktopViewState) -> None:
                if current.visual.current_image:
                    system_line("[immagine rigenerata]")
                refresh(current)

            run_async(self._controller.retry_image, presented, "rerendering in corso…")

        def toggle_debug() -> None:
            current = self._controller.state
            refresh(self._controller.set_visual_debug(not current.visual.show_debug))

        def new_session() -> None:
            answer = qt_widgets.QMessageBox.question(
                window,
                "Nuova sessione",
                "Creare una nuova sessione? Quella attuale resta salvata.",
                qt_widgets.QMessageBox.Yes | qt_widgets.QMessageBox.No,
                qt_widgets.QMessageBox.No,
            )
            if answer != qt_widgets.QMessageBox.Yes:
                return

            def presented(current: DesktopViewState) -> None:
                clear_story()
                image_label.clear_image()
                system_line(f"[nuova sessione: {current.session.session_id}]")
                refresh(current)

            run_async(self._controller.new_session, presented, "creazione nuova sessione…")

        def reload_session() -> None:
            def presented(current: DesktopViewState) -> None:
                system_line("[sessione ricaricata dal salvataggio]")
                refresh(current)

            run_async(self._controller.resume_session, presented, "caricamento sessione…")

        def open_image() -> None:
            path = image_label.source_path
            if path is None or not path.exists():
                return
            viewer = ImageViewer(path, window)
            image_viewers.append(viewer)
            viewer.finished.connect(lambda _result, item=viewer: image_viewers.remove(item))
            viewer.show()
            viewer.raise_()
            viewer.activateWindow()

        send_button.clicked.connect(submit)
        player_input.submit_requested.connect(submit)
        retry_button.clicked.connect(retry)
        debug_toggle.clicked.connect(toggle_debug)
        new_button.clicked.connect(new_session)
        reload_button.clicked.connect(reload_session)
        image_label.clicked.connect(open_image)

        refresh(view)
        phase_label.setText("Fase: pronta — scrivi liberamente la tua azione")
        window.show()
        player_input.setFocus()
        return int(app.exec())


def launch_desktop(
    runtime: EPOSRuntimePort,
    *,
    session_id: SessionId,
) -> int:
    return QtDesktopLauncher(DesktopController(runtime), session_id).run()
