@echo off
cd /d "%~dp0"
echo Updating data from upstream...
git pull --rebase upstream main
echo Building dashboard...
python build_dashboard.py || (echo Build failed & pause & exit /b 1)
start "" dashboard.html
