# EPOS NEXT

EPOS NEXT is a Python-authoritative narrative RPG engine with structured OpenAI
reasoning, persistent world state, player-intent interpretation, NPC cognition,
outfit continuity and an AUTOMATIC1111/Forge visual pipeline.

## Windows local setup

Requirements:

- Python 3.11 or newer (Python 3.12 recommended);
- Git;
- AUTOMATIC1111/Forge launched with `--api` and reachable at `http://127.0.0.1:7860`;
- an OpenAI API key;
- the checkpoint named in `.env` installed in `models/Stable-diffusion`;
- the Worldpack LoRAs installed in the WebUI LoRA directory.

Model files stay in the WebUI installation. Do not copy checkpoints or LoRAs
into the EPOS NEXT repository.

From PowerShell in `D:\EPOS-NEXT`:

```powershell
git switch main
git pull --ff-only
.\.venv\Scripts\python.exe -m pip install -e ".[dev,server,gui]"
Copy-Item .env.example .env
notepad .env
```

At minimum, check these local `.env` values:

```dotenv
OPENAI_API_KEY=your-key-here
EPOS_PRIMARY_LLM_MODEL=gpt-5.6-terra
EPOS_RENDER_MODE=a1111
A1111_BASE_URL=http://127.0.0.1:7860
A1111_CHECKPOINT=cyberrealisticPony_v7.safetensors
```

Never commit `.env`; it is ignored by Git. The OpenAI provider uses the Responses
API with `store: false`. `gpt-5.6-terra` is only the default and can be changed in
the local file.

Start the WebUI with `--api` first, then double-click `avvia_epos.bat`. To verify the two external
connections without opening the GUI:

```powershell
.\.venv\Scripts\python.exe -m epos.cli check
```

Runtime state, generated images, pending renders and diagnostics are stored under
the ignored `runtime_data` directory. The launcher resumes the last selected
session; delete only `runtime_data/current_session.txt` if you deliberately want a
new default session.

## Development gates

On Windows, use a project-owned temporary directory if the system pytest temp
directory is inaccessible:

```powershell
New-Item -ItemType Directory -Force D:\EPOS_TEST_TEMP | Out-Null
$env:TEMP = "D:\EPOS_TEST_TEMP"
$env:TMP = "D:\EPOS_TEST_TEMP"
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe -m ruff check .
.\.venv\Scripts\python.exe -m mypy src
```
