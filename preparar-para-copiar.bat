@echo off
echo ========================================
echo   Preparar Proyecto para Copiar
echo ========================================
echo.

REM Crear carpeta temporal para el .zip
set TEMP_DIR=proyecto_para_copiar
if exist %TEMP_DIR% (
    echo Limpiando carpeta temporal...
    rmdir /s /q %TEMP_DIR%
)

mkdir %TEMP_DIR%

echo [1/5] Copiando archivos Python...
copy *.py %TEMP_DIR%\ >nul 2>&1
echo    ✅ Archivos Python copiados

echo [2/5] Copiando archivos de configuración...
copy requirements.txt %TEMP_DIR%\ >nul 2>&1
copy *.txt %TEMP_DIR%\ >nul 2>&1
copy *.bat %TEMP_DIR%\ >nul 2>&1
copy *.md %TEMP_DIR%\ >nul 2>&1
copy *.yaml %TEMP_DIR%\ >nul 2>&1
copy *.yml %TEMP_DIR%\ >nul 2>&1
echo    ✅ Archivos de configuración copiados

echo [3/5] Copiando base de datos (para mantener los datos)...
if exist social_media_analytics.db (
    copy social_media_analytics.db %TEMP_DIR%\ >nul 2>&1
    echo    ✅ Base de datos copiada (datos preservados)
) else (
    echo    ⚠️  No se encontró base de datos (se creará nueva en la otra PC)
)

echo [4/5] Copiando documentación...
if exist *.md (
    copy *.md %TEMP_DIR%\ >nul 2>&1
    echo    ✅ Documentación copiada
)

echo [5/5] Creando .zip...
powershell -Command "Compress-Archive -Path '%TEMP_DIR%\*' -DestinationPath 'proyecto_backend.zip' -Force"
if errorlevel 1 (
    echo    ❌ ERROR: No se pudo crear el .zip
    echo    Asegúrate de tener permisos de escritura
    pause
    exit /b 1
)

echo    ✅ Archivo proyecto_backend.zip creado

REM Limpiar carpeta temporal
rmdir /s /q %TEMP_DIR%

echo.
echo ========================================
echo   ✅ Proyecto Listo para Copiar
echo ========================================
echo.
echo Archivo creado: proyecto_backend.zip
echo.
echo IMPORTANTE:
echo - La base de datos ESTÁ incluida (tus datos se preservarán)
echo - El entorno virtual NO está incluido (se creará en la otra PC)
echo.
echo Próximos pasos:
echo 1. Copia 'proyecto_backend.zip' a la otra computadora
echo 2. Extrae el .zip
echo 3. Ejecuta 'setup-nueva-pc.bat' en la otra PC
echo.
pause
