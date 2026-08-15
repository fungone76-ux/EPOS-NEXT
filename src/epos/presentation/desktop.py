"""PySide6 desktop adapter plus a framework-independent tested controller."""

from __future__ import annotations

import asyncio
import importlib
import json

from epos.application.turn import TurnCommand
from epos.domain.errors import ConfigurationError
from epos.domain.ids import SessionId
from epos.presentation.models import (
    DesktopViewState,
    StoryPanelState,
    VisualPanelState,
)
from epos.presentation.ports import EPOSRuntimePort


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

    def set_visual_debug(self, enabled: bool) -> DesktopViewState:
        current = self.state
        self._state = current.model_copy(
            update={"visual": current.visual.model_copy(update={"show_debug": enabled})},
            deep=True,
        )
        return self.state


class QtDesktopLauncher:
    """Thin optional Qt shell; all behavior remains in `DesktopController`."""

    def __init__(self, controller: DesktopController, session_id: SessionId) -> None:
        self._controller = controller
        self._session_id = session_id

    def run(self) -> int:
        try:
            qt_widgets = importlib.import_module("PySide6.QtWidgets")
            qt_gui = importlib.import_module("PySide6.QtGui")
        except ModuleNotFoundError as exc:
            raise ConfigurationError(
                "PySide6 is required for the desktop GUI; install epos-next[gui]"
            ) from exc

        asyncio.run(self._controller.initialize(self._session_id))
        app = qt_widgets.QApplication.instance() or qt_widgets.QApplication([])
        window = qt_widgets.QMainWindow()
        window.setWindowTitle("EPOS NEXT")
        root = qt_widgets.QWidget()
        layout = qt_widgets.QHBoxLayout(root)

        state_text = qt_widgets.QTextEdit()
        state_text.setReadOnly(True)
        story_text = qt_widgets.QTextEdit()
        story_text.setReadOnly(True)
        player_input = qt_widgets.QLineEdit()
        send_button = qt_widgets.QPushButton("Invia")
        image_label = qt_widgets.QLabel("Nessuna immagine")
        debug_toggle = qt_widgets.QCheckBox("Show Visual Debug")
        debug_text = qt_widgets.QTextEdit()
        debug_text.setReadOnly(True)
        retry_button = qt_widgets.QPushButton("Retry Image")

        state_column = qt_widgets.QVBoxLayout()
        state_column.addWidget(qt_widgets.QLabel("Stato"))
        state_column.addWidget(state_text)
        story_column = qt_widgets.QVBoxLayout()
        story_column.addWidget(qt_widgets.QLabel("Storia"))
        story_column.addWidget(story_text)
        story_column.addWidget(player_input)
        story_column.addWidget(send_button)
        visual_column = qt_widgets.QVBoxLayout()
        visual_column.addWidget(qt_widgets.QLabel("Visuale"))
        visual_column.addWidget(image_label)
        visual_column.addWidget(debug_toggle)
        visual_column.addWidget(debug_text)
        visual_column.addWidget(retry_button)
        layout.addLayout(state_column, 1)
        layout.addLayout(story_column, 2)
        layout.addLayout(visual_column, 2)
        window.setCentralWidget(root)
        status = window.statusBar()

        def refresh(view: DesktopViewState) -> None:
            state_text.setPlainText(
                json.dumps(view.session.model_dump(mode="json"), ensure_ascii=False, indent=2)
            )
            story_text.setPlainText(view.story.narration)
            visual = view.visual.result
            debug_text.setVisible(view.visual.show_debug)
            debug_text.setPlainText(
                "" if visual is None else json.dumps(visual.model_dump(mode="json"), indent=2)
            )
            retry_button.setEnabled(bool(visual and visual.retry_available))
            if view.visual.current_image:
                pixmap = qt_gui.QPixmap(view.visual.current_image)
                image_label.setPixmap(pixmap)
            else:
                image_label.setText("Nessuna immagine")
            status.showMessage(
                f"LLM {view.health.llm.status} | Renderer {view.health.renderer.status} | "
                f"Worldpack {view.session.worldpack_id} | Sessione {view.session.session_id}"
            )

        def submit() -> None:
            text = player_input.text().strip()
            if not text:
                return
            refresh(asyncio.run(self._controller.submit_player_input(text)))
            player_input.clear()

        def retry() -> None:
            refresh(asyncio.run(self._controller.retry_image()))

        def toggle(enabled: bool) -> None:
            refresh(self._controller.set_visual_debug(enabled))

        send_button.clicked.connect(submit)
        player_input.returnPressed.connect(submit)
        retry_button.clicked.connect(retry)
        debug_toggle.toggled.connect(toggle)
        refresh(self._controller.state)
        window.resize(1400, 800)
        window.show()
        return int(app.exec())


def launch_desktop(
    runtime: EPOSRuntimePort,
    *,
    session_id: SessionId,
) -> int:
    return QtDesktopLauncher(DesktopController(runtime), session_id).run()
