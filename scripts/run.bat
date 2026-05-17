@echo off
setlocal

cd /d "%~dp0\.."

git fetch --prune
if errorlevel 1 exit /b %errorlevel%

git pull --ff-only
if errorlevel 1 exit /b %errorlevel%

uv sync
if errorlevel 1 exit /b %errorlevel%

uv run python main.py
exit /b %errorlevel%
