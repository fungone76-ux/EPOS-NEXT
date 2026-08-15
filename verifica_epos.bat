@echo off
setlocal
cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
  echo ERRORE: ambiente Python .venv non trovato.
  pause
  exit /b 1
)

if not exist "runtime_data\test_temp" mkdir "runtime_data\test_temp"
set "TEMP=%CD%\runtime_data\test_temp"
set "TMP=%CD%\runtime_data\test_temp"

".venv\Scripts\python.exe" -m pytest -q
if errorlevel 1 goto :failed
".venv\Scripts\python.exe" -m ruff check .
if errorlevel 1 goto :failed
".venv\Scripts\python.exe" -m mypy src
if errorlevel 1 goto :failed

echo.
echo EPOS NEXT verificato correttamente.
pause
exit /b 0

:failed
echo.
echo Verifica fallita. Leggi il messaggio sopra.
pause
exit /b 1
