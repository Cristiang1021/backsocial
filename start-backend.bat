@echo off
echo ========================================
echo   Iniciando Backend Local con ngrok
echo ========================================
echo.

REM Cambiar al directorio del script
cd /d "%~dp0"

REM Activar entorno virtual
echo [1/3] Activando entorno virtual...
call venv\Scripts\activate.bat
if errorlevel 1 (
    echo ERROR: No se pudo activar el entorno virtual
    echo Asegurate de que venv existe: python -m venv venv
    pause
    exit /b 1
)

REM Iniciar backend en nueva ventana
echo [2/3] Iniciando servidor backend en puerto 8000...
start "Backend API" cmd /k "cd /d %~dp0 && venv\Scripts\activate.bat && echo Backend corriendo en http://localhost:8000 && uvicorn api:app --host 0.0.0.0 --port 8000"

REM Esperar un poco para que el backend inicie
timeout /t 5 /nobreak >nul

REM Iniciar ngrok en nueva ventana
echo [3/3] Iniciando ngrok...
start "ngrok Tunnel" cmd /k "echo ngrok iniciado - Copia la URL Forwarding y actualiza: && echo   1. front_template/template/lib/api.ts (NGROK_URL) && echo   2. api.py (NGROK_URL en CORS) && echo. && ngrok http 8000"

echo.
echo ========================================
echo   Backend iniciado correctamente!
echo ========================================
echo.
echo Backend: http://localhost:8000
echo ngrok: Revisa la ventana de ngrok para obtener la URL
echo.
echo IMPORTANTE:
echo 1. Copia la URL de ngrok (ej: https://abc123.ngrok-free.app)
echo 2. Actualiza NGROK_URL en front_template/template/lib/api.ts
echo 3. Actualiza NGROK_URL en api.py (para CORS)
echo 4. Reinicia el backend si cambiaste CORS
echo.
pause
