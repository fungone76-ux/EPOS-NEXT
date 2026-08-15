@echo off
setlocal
cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
  echo ERRORE: ambiente Python .venv non trovato.
  echo Esegui prima: py -3.12 -m venv .venv
  pause
  exit /b 1
)

if not exist ".env" (
  echo ERRORE: file .env non trovato.
  echo Copia .env.example in .env e inserisci la tua OPENAI_API_KEY.
  pause
  exit /b 1
)

".venv\Scripts\python.exe" -m epos.cli --project-root "%~dp0" desktop
if errorlevel 1 (
  echo.
  echo EPOS NEXT si e' chiuso con un errore. Leggi il messaggio sopra.
  pause
)
endlocal
