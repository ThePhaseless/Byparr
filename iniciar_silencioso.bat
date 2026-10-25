@echo off
cd /d "%~dp0"

:: 1. Verificacao e atualizacao automatica via git e uv (apenas se estiver na branch main)
set CURRENT_BRANCH=
for /f %%c in ('git branch --show-current 2^>nul') do set CURRENT_BRANCH=%%c

if "%CURRENT_BRANCH%"=="main" (
    git fetch origin main --quiet 2>nul
    if %ERRORLEVEL% equ 0 (
        for /f %%a in ('git rev-parse HEAD 2^>nul') do set LOCAL_REV=%%a
        for /f %%b in ('git rev-parse origin/main 2^>nul') do set REMOTE_REV=%%b
        if defined LOCAL_REV if defined REMOTE_REV (
            if not "%LOCAL_REV%"=="%REMOTE_REV%" (
                echo [%date% %time%] Nova versao detectada no GitHub. Atualizando Byparr... >> byparr.log
                git pull origin main >> byparr.log 2>&1
                where uv >nul 2>&1
                if %ERRORLEVEL% equ 0 (
                    uv sync --system-certs >> byparr.log 2>&1
                ) else (
                    if exist "%USERPROFILE%\.local\bin\uv.exe" (
                        "%USERPROFILE%\.local\bin\uv.exe" sync --system-certs >> byparr.log 2>&1
                    )
                )
            )
        )
    )
)

:: 2. Inicia o servidor Byparr
"C:\Program Files\byparr\.venv\Scripts\python.exe" main.py >> byparr.log 2>&1
