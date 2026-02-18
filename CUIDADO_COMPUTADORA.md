# 💻 Cuidado de Computadora para Backend 24/7

Guía para mantener tu computadora funcionando de forma segura y eficiente mientras corre el backend.

## ⚙️ Configuraciones de Windows para Mantener la PC Encendida

### 1. Prevenir que la PC se Duerma

**Configuración de Energía:**
1. Ve a **Configuración** → **Sistema** → **Energía y suspensión**
2. Configura:
   - **Cuando está conectada a la corriente**: "Nunca" (para pantalla y suspensión)
   - **Cuando funciona con batería**: "Nunca" (si usas laptop)

**O desde Panel de Control:**
1. Panel de Control → **Opciones de energía**
2. **Cambiar la configuración del plan** (Plan equilibrado o Alto rendimiento)
3. Configura:
   - **Activar pantalla**: Nunca
   - **Suspender el equipo**: Nunca
   - **Desactivar disco duro**: Nunca (o después de 30 min)

### 2. Prevenir Apagado Automático

**Desactivar actualizaciones automáticas que reinician:**
1. **Configuración** → **Actualización y seguridad** → **Windows Update**
2. **Opciones avanzadas** → **Pausar actualizaciones** (hasta 7 días)
3. O configura **Horas activas** para que no reinicie durante el día

**Usando PowerShell (como administrador):**
```powershell
# Desactivar reinicio automático por actualizaciones
Set-ItemProperty -Path "HKLM:\SOFTWARE\Microsoft\WindowsUpdate\UX\Settings" -Name "UxOption" -Value 1
```

### 3. Optimizar Rendimiento

**Desactivar efectos visuales innecesarios:**
1. Panel de Control → **Sistema** → **Configuración avanzada del sistema**
2. **Rendimiento** → **Configuración**
3. Selecciona **Ajustar para obtener el mejor rendimiento** o **Personalizado** (desactiva animaciones)

**Cerrar programas innecesarios:**
- Cierra navegadores con muchas pestañas
- Cierra programas que no uses
- Usa el **Administrador de tareas** para ver qué consume recursos

### 4. Monitoreo de Temperatura (Laptops)

**Para laptops, es importante:**
- Usa una **base con ventiladores** si es posible
- Mantén las **rejillas de ventilación limpias**
- No uses la laptop sobre la cama/almohadas (bloquea ventilación)
- Considera **limpiar el polvo interno** cada 6 meses

**Herramientas de monitoreo:**
- **Core Temp** (gratis): Monitorea temperatura del CPU
- **HWMonitor** (gratis): Monitorea temperatura de todos los componentes

### 5. Configurar Reinicio Automático (Opcional)

Si quieres que la PC se reinicie automáticamente cada X días:

**Programador de tareas:**
1. **Programador de tareas** → **Crear tarea básica**
2. Configura para reiniciar a las 3 AM cada X días
3. **Acción**: `shutdown /r /t 0`

## 🔄 Usar Computadora del Trabajo con ngrok

### ✅ SÍ, Funciona Perfectamente

Puedes usar tu computadora del trabajo con la **misma cuenta de ngrok**. Solo necesitas:

### Requisitos:

1. **Misma cuenta de ngrok:**
   - Inicia sesión con la misma cuenta en ambas computadoras
   - O usa el mismo authtoken

2. **Mismo authtoken:**
   ```bash
   # En la computadora del trabajo, configura el mismo token:
   ngrok config add-authtoken TU_TOKEN_AQUI
   ```

3. **Misma URL de ngrok:**
   - Si usas plan **gratuito**: La URL cambiará cada vez que reinicies ngrok
   - Si usas plan **Pro ($5/mes)**: Puedes tener URL fija

### ⚠️ Consideraciones Importantes:

#### 1. **URL de ngrok cambia (Plan Gratuito)**
- Cada vez que inicias ngrok en una computadora diferente, obtienes una URL nueva
- Necesitas actualizar el frontend cada vez que cambies de computadora

**Solución:**
- Usa **ngrok Pro** ($5/mes) para URL fija
- O actualiza manualmente `front_template/template/lib/api.ts` cada vez

#### 2. **Sincronizar Código**
- Asegúrate de tener el mismo código en ambas computadoras
- Usa **Git** para sincronizar:
  ```bash
  # En computadora 1:
  git add .
  git commit -m "Cambios"
  git push

  # En computadora 2 (trabajo):
  git pull
  ```

#### 3. **Base de Datos**
- Si usas SQLite, cada computadora tendrá su propia BD
- **Solución**: Usa una BD compartida (Google Drive, OneDrive) o PostgreSQL remoto

#### 4. **Políticas de la Empresa**
- Verifica que tu empresa permita ejecutar servidores
- Algunas empresas bloquean puertos o tienen firewalls estrictos
- Considera usar un **puerto no estándar** si hay restricciones

### 📋 Checklist para Cambiar de Computadora:

1. ✅ Código sincronizado (Git)
2. ✅ ngrok instalado y configurado con mismo token
3. ✅ Python y dependencias instaladas
4. ✅ Variables de entorno configuradas (si las usas)
5. ✅ Actualizar URL de ngrok en frontend
6. ✅ Verificar que el puerto 8000 esté disponible

## 🎯 Recomendaciones

### Para Uso Personal (4 horas/día):
- ✅ Configura Windows para no dormirse
- ✅ Usa modo "Alto rendimiento" cuando corra el backend
- ✅ Monitorea temperatura (especialmente laptops)
- ✅ Programa reinicios periódicos (cada 2-3 días)

### Para Uso en Trabajo:
- ✅ Verifica políticas de la empresa
- ✅ Usa ngrok Pro para URL fija (evita actualizar frontend)
- ✅ Sincroniza código con Git
- ✅ Considera usar PostgreSQL remoto para BD compartida

### Alternativa: Servidor Dedicado
Si necesitas 24/7 sin depender de tu PC:
- **VPS barato**: DigitalOcean ($6/mes), Linode ($5/mes)
- **Render/Heroku**: Ya lo probaste, pero con límites de RAM
- **Raspberry Pi**: ~$50 una vez, consume poca energía

## 🔧 Script para Iniciar Backend en Cualquier PC

Crea `start-backend-portable.bat`:

```batch
@echo off
echo Iniciando backend en esta computadora...

REM Verificar Python
python --version >nul 2>&1
if errorlevel 1 (
    echo ERROR: Python no encontrado
    pause
    exit /b 1
)

REM Activar venv (si existe)
if exist venv\Scripts\activate.bat (
    call venv\Scripts\activate.bat
) else (
    echo Creando entorno virtual...
    python -m venv venv
    call venv\Scripts\activate.bat
    pip install -r requirements.txt
)

REM Iniciar backend
start "Backend API" cmd /k "uvicorn api:app --host 0.0.0.0 --port 8000"

REM Esperar y iniciar ngrok
timeout /t 3 /nobreak >nul
start "ngrok" cmd /k "ngrok http 8000"

echo.
echo ✅ Backend iniciado
echo 📋 Copia la URL de ngrok y actualiza el frontend
pause
```

---

**¡Con estos consejos, tu computadora aguantará perfectamente 4+ horas al día!** 💪
