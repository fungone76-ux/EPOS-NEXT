"""Command-line entry points for the local EPOS NEXT runtime."""

from __future__ import annotations

import argparse
import asyncio
from pathlib import Path

from epos.presentation import launch_desktop
from epos.runtime import build_local_runtime


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="epos-next")
    parser.add_argument(
        "--project-root",
        type=Path,
        default=Path.cwd(),
        help="EPOS NEXT repository directory (default: current directory)",
    )
    parser.add_argument(
        "command",
        nargs="?",
        choices=("desktop", "check"),
        default="desktop",
    )
    return parser


def main() -> int:
    args = _parser().parse_args()
    runtime = build_local_runtime(args.project_root)
    if args.command == "check":
        session = asyncio.run(runtime.open_default_session())
        health = asyncio.run(runtime.health())
        print(f"Sessione: {session.session_id}")
        print(f"OpenAI: {health.llm.status} ({health.llm.detail})")
        print(f"A1111: {health.renderer.status} ({health.renderer.detail or 'ok'})")
        return 0 if health.renderer.status == "up" else 2

    session = asyncio.run(runtime.open_default_session())
    return launch_desktop(runtime, session_id=session.session_id)


if __name__ == "__main__":
    raise SystemExit(main())
