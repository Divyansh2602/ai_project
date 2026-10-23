@echo off
setlocal
title TrustSphere AI
cd /d "%~dp0backend"

REM Use the first Python that has the app's packages: local venv, TS_PYTHON, another TrustSphere venv, then PATH.
set "PY="
for %%P in ("%~dp0backend\venv\Scripts\python.exe" "%TS_PYTHON%" "%USERPROFILE%\Desktop\trustsphere-ai\backend\venv\Scripts\python.exe" "python") do (
  if not defined PY (
    "%%~P" -c "import fastapi, uvicorn, sqlalchemy, torch, transformers, reportlab" >nul 2>&1 && set "PY=%%~P"
  )
)
if not defined PY (
  echo.
  echo   ERROR: no Python with the required packages was found.
  echo   Create a venv in backend and run: pip install -r requirements.txt
  echo   or set TS_PYTHON to a Python that has them.
  pause
  exit /b 1
)

if not exist ".env" (
  echo   Note: backend\.env not found. Create it with DATABASE_URL=sqlite:///./trustsphere.db and CELERY_ALWAYS_EAGER=true for local mode.
)
echo.
echo   TrustSphere AI  -  http://127.0.0.1:8000/app/
echo   Python: %PY%
echo   Keep this window OPEN. Closing it stops the server.
echo.
start "" /min powershell -NoProfile -Command "for($i=0;$i -lt 90;$i++){ try{ Invoke-WebRequest -UseBasicParsing -TimeoutSec 2 http://127.0.0.1:8000/health | Out-Null; Start-Process 'http://127.0.0.1:8000/app/'; break } catch { Start-Sleep -Seconds 1 } }"
"%PY%" -m uvicorn main:app --host 127.0.0.1 --port 8000
echo.
echo   The server stopped. Scroll up for the reason.
pause
