from pathlib import Path


def test_windows_launcher_uses_current_directory_without_trailing_slash_argument() -> None:
    project_root = Path(__file__).resolve().parents[2]
    launcher = (project_root / "avvia_epos.bat").read_text(encoding="utf-8")

    assert 'cd /d "%~dp0"' in launcher
    assert '".venv\\Scripts\\python.exe" -m epos.cli desktop' in launcher
    assert '--project-root "%~dp0"' not in launcher
