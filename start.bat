@echo off
REM Lead Scout — double-click launcher for Windows.
REM Installs anything missing, then starts the web UI on localhost:5000.

cd /d "%~dp0"

REM Find a Python: the py launcher first, then python on PATH.
set PY=py
%PY% --version >nul 2>&1
if errorlevel 1 (
    set PY=python
    python --version >nul 2>&1
    if errorlevel 1 (
        echo.
        echo   Python isn't installed, or isn't on your PATH.
        echo   Get it from https://python.org/downloads
        echo   IMPORTANT: tick "Add python.exe to PATH" on the first screen.
        echo.
        pause
        exit /b 1
    )
)

echo.
echo   Checking dependencies...
%PY% -m pip install -q -r requirements.txt
if errorlevel 1 (
    echo.
    echo   Install failed. Try running this by hand to see the error:
    echo      %PY% -m pip install -r requirements.txt
    echo.
    pause
    exit /b 1
)

if not exist .env (
    copy .env.example .env >nul
    echo   Created .env — add a free CEREBRAS_API_KEY to unlock "Work the lead".
)

echo   Starting Lead Scout...
echo.
%PY% web.py

REM Keep the window open if the server exits with an error.
if errorlevel 1 pause
