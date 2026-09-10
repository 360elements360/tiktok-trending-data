@echo off
cd /d "%~dp0"
echo Updating data from upstream...
git pull --no-rebase --no-edit upstream main
git push origin main >nul 2>&1
echo Building dashboard...
python build_dashboard.py || (echo Build failed & pause & exit /b 1)
start "" dashboard.html
