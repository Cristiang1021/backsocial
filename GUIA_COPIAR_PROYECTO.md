# 📦 Guía: Copiar Proyecto a Otra Computadora

Esta guía te explica cómo copiar tu proyecto en un .zip y ejecutarlo en otra computadora (ej: trabajo).

## ✅ Lo que SÍ Funciona Igual

- ✅ Todo el código Python
- ✅ Configuraciones hardcodeadas (URLs, etc.)
- ✅ Estructura de archivos
- ✅ Scripts (.bat, .md, etc.)

## ⚠️ Lo que NO se Copia (y Necesitas Recrear)

### 1. Entorno Virtual (`venv/`)
- **NO incluyas** la carpeta `venv/` en el .zip (es muy pesada y específica de cada PC)
- Se recrea fácilmente en la otra PC

### 2. Base de Datos SQLite
- Si incluyes `social_media_analytics.db`, tendrás los mismos datos
- Si NO lo incluyes, se creará una BD nueva y limpia
- **Recomendación**: NO incluyas la BD si quieres empezar limpio

### 3. Configuración de ngrok
- El authtoken se guarda en `%USERPROFILE%\.ngrok2\ngrok.yml` (no en el proyecto)
- Necesitas configurarlo en la otra PC

## 📋 Checklist: Qué Incluir en el .zip

### ✅ INCLUIR (IMPORTANTE - Para que NO se pierdan datos):
```
✅ api.py
✅ config.py
✅ db_utils.py
✅ scraper.py
✅ analyzer.py
✅ utils.py
✅ app.py (si lo usas)
✅ requirements.txt
✅ start-backend.bat
✅ setup-nueva-pc.bat (script de configuración)
✅ social_media_analytics.db ⭐ (INCLUIR para mantener los datos)
✅ *.md (documentación)
✅ front_template/ (si también copias el frontend)
```

### ❌ NO INCLUIR:
```
❌ venv/ (carpeta del entorno virtual - se recrea)
❌ __pycache__/ (archivos compilados de Python)
❌ *.pyc (archivos compilados)
❌ .git/ (si usas Git, opcional)
```

### 🎯 Script Automático

**Usa `preparar-para-copiar.bat`** para crear el .zip automáticamente:
- ✅ Incluye todos los archivos necesarios
- ✅ **INCLUYE la base de datos** (para preservar datos)
- ✅ Excluye lo que no necesitas (venv, cache, etc.)

Simplemente ejecuta:
```bash
preparar-para-copiar.bat
```

Esto creará `proyecto_backend.zip` listo para copiar.

## 🚀 Pasos para Ejecutar en la Otra PC

### 1. Extraer el .zip
```bash
# Extrae el .zip en cualquier carpeta, ej:
C:\Users\TuUsuario\Desktop\Test\
```

### 2. Verificar Python
```bash
python --version
# Debe ser Python 3.11 o superior
```

Si no tienes Python:
- Descarga desde [python.org](https://www.python.org/downloads/)
- Marca "Add Python to PATH" durante la instalación

### 3. Crear Entorno Virtual
```bash
cd C:\Users\TuUsuario\Desktop\Test
python -m venv venv
```

### 4. Activar Entorno Virtual
```bash
venv\Scripts\activate
```

### 5. Instalar Dependencias
```bash
pip install -r requirements.txt
```

### 6. Configurar ngrok
```bash
# Si ngrok no está instalado:
# Descarga desde https://ngrok.com/download

# Configura el mismo token que en tu PC de casa:
ngrok config add-authtoken TU_TOKEN_AQUI
```

### 7. Iniciar Backend
```bash
# Opción 1: Usar el script
start-backend.bat

# Opción 2: Manual
uvicorn api:app --host 0.0.0.0 --port 8000
```

### 8. Iniciar ngrok (en otra terminal)
```bash
ngrok http 8000
```

### 9. Actualizar Frontend (si la URL cambió)
Si usas plan gratuito de ngrok, la URL cambiará. Actualiza:
- `front_template/template/lib/api.ts` línea 10:
  ```typescript
  const NGROK_URL = 'https://NUEVA_URL_NGROK.ngrok-free.app/api'
  ```

## 🔧 Script Automático para la Otra PC

Crea `setup-nueva-pc.bat` en el .zip:

```batch
@echo off
echo ========================================
echo   Configuración Inicial del Proyecto
echo ========================================
echo.

REM Verificar Python
python --version >nul 2>&1
if errorlevel 1 (
    echo ❌ ERROR: Python no encontrado
    echo    Descarga Python desde https://www.python.org/downloads/
    pause
    exit /b 1
)

echo ✅ Python encontrado
echo.

REM Crear entorno virtual
echo [1/4] Creando entorno virtual...
if exist venv (
    echo    Entorno virtual ya existe, omitiendo...
) else (
    python -m venv venv
    echo    ✅ Entorno virtual creado
)

REM Activar entorno virtual
echo [2/4] Activando entorno virtual...
call venv\Scripts\activate.bat

REM Instalar dependencias
echo [3/4] Instalando dependencias...
pip install -r requirements.txt
if errorlevel 1 (
    echo ❌ ERROR: No se pudieron instalar las dependencias
    pause
    exit /b 1
)
echo    ✅ Dependencias instaladas

REM Verificar ngrok
echo [4/4] Verificando ngrok...
ngrok version >nul 2>&1
if errorlevel 1 (
    echo    ⚠️  ngrok no encontrado
    echo    Descarga desde https://ngrok.com/download
    echo    Luego ejecuta: ngrok config add-authtoken TU_TOKEN
) else (
    echo    ✅ ngrok encontrado
)

echo.
echo ========================================
echo   ✅ Configuración Completada
echo ========================================
echo.
echo Próximos pasos:
echo 1. Configura ngrok: ngrok config add-authtoken TU_TOKEN
echo 2. Ejecuta: start-backend.bat
echo 3. Copia la URL de ngrok y actualiza el frontend
echo.
pause
```

## 📝 Notas Importantes

### Base de Datos - ⭐ IMPORTANTE PARA NO PERDER DATOS

**El script `preparar-para-copiar.bat` INCLUYE la BD automáticamente**

- ✅ **Si incluyes** `social_media_analytics.db` en el .zip:
  - **Tus datos se preservarán** en la otra PC
  - Podrás continuar exactamente donde dejaste
  - **RECOMENDADO** para no perder información

- ⚠️ Si **NO incluyes** `social_media_analytics.db`:
  - Se creará una BD nueva y limpia automáticamente
  - **PERDERÁS todos los datos** (posts, comentarios, perfiles, etc.)
  - Solo úsalo si quieres empezar desde cero

**💡 Recomendación:** SIEMPRE incluye la BD para preservar tus datos.

### ngrok - URL Fija vs Cambiante

**Plan Gratuito:**
- ❌ URL cambia cada vez que reinicias ngrok
- ❌ Necesitas actualizar el frontend cada vez
- ✅ Gratis

**Plan Pro ($5/mes):**
- ✅ URL fija (ej: `https://www.backsocual.ngrok.app`)
- ✅ No necesitas actualizar el frontend
- ✅ Funciona igual en ambas PCs

### Sincronización de Datos

Si quieres que ambas PCs compartan los mismos datos:

**Opción 1: PostgreSQL Remoto (Render)**
- Usa la misma BD PostgreSQL en ambas PCs
- Datos sincronizados automáticamente

**Opción 2: Sincronizar SQLite (Complicado)**
- Usa Google Drive/OneDrive para sincronizar el archivo `.db`
- ⚠️ Riesgo de conflictos si ambas PCs escriben al mismo tiempo

**Opción 3: BD Separadas (Recomendado)**
- Cada PC tiene su propia BD SQLite
- Más simple y sin conflictos

## ✅ Resumen Rápido (Para NO Perder Datos)

1. **Ejecuta** `preparar-para-copiar.bat` (incluye la BD automáticamente)
2. **Copia** `proyecto_backend.zip` a la otra PC
3. **Extrae** el .zip (verifica que `social_media_analytics.db` esté presente)
4. **Ejecuta** `setup-nueva-pc.bat` en la otra PC
5. **Configura** ngrok con tu token: `ngrok config add-authtoken TU_TOKEN`
6. **Inicia** el backend con `start-backend.bat`
7. **Actualiza** el frontend si la URL de ngrok cambió

**✅ Tus datos estarán preservados y todo funcionará igual.** 🎉

## 🔒 Garantía de Datos

**Con `preparar-para-copiar.bat`:**
- ✅ La BD se incluye automáticamente
- ✅ Todos tus datos se preservan
- ✅ No perderás posts, comentarios, perfiles, etc.
- ✅ Funciona exactamente igual en ambas PCs

---

**Tip:** Si usas Git, es más fácil:
```bash
# En PC de casa:
git push

# En PC del trabajo:
git clone TU_REPOSITORIO
cd TU_REPOSITORIO
# Seguir pasos 3-9 arriba
```
