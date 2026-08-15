# Module 21 — Desktop GUI

The desktop presentation is split into a framework-independent `DesktopController` and a
thin optional PySide6 adapter.

The UI exposes three primary areas:

- state: location, time, present NPCs, known information, missions, events and skills;
- story: player input, narration and NPC dialogue;
- visual: current image, render status, full visual debug contract and Retry Image.

The status bar reports LLM, renderer, Worldpack and session status. Both desktop and later
HTTP adapters depend on the same `EPOSRuntimePort` and stable Module 19 contracts. The GUI
does not receive private cognition or authoritative mutation access.

Install the optional `epos-next[gui]` dependency to launch the PySide6 adapter. Controller
tests remain headless and deterministic.
