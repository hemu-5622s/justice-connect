@echo off
setlocal
set "ROOT=%~dp0"
set "PYTHON=%ROOT%.venv\Scripts\python.exe"

if not exist "%PYTHON%" (
    echo Project Python environment not found:
    echo %PYTHON%
    pause
    exit /b 1
)

powershell -NoProfile -ExecutionPolicy Bypass -Command "if (-not (Get-NetTCPConnection -LocalPort 8501 -State Listen -ErrorAction SilentlyContinue)) { Start-Process -FilePath '%PYTHON%' -ArgumentList '-m streamlit run app.py --server.address 0.0.0.0 --server.headless true' -WorkingDirectory '%ROOT%' }"
timeout /t 3 /nobreak >nul
start "" "http://localhost:8501"
endlocal
