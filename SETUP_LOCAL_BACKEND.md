# 🖥️ Configuración de Backend Local con ngrok

Esta guía te ayudará a ejecutar el backend en tu computadora local y exponerlo a internet usando ngrok.

## ✅ Ventajas de Backend Local

- ✅ **Sin límites de RAM**: Tu computadora tiene más memoria que el plan Starter (512 MB)
- ✅ **Más económico**: Solo necesitas ngrok (gratis con limitaciones o $5/mes)
- ✅ **Mejor rendimiento**: Sin cold starts ni límites de CPU
- ✅ **Control total**: Puedes reiniciar, actualizar y monitorear fácilmente

## 📋 Requisitos Previos

1. **Python 3.11+** instalado
2. **ngrok** instalado ([descargar aquí](https://ngrok.com/download))
3. **Conexión a internet** estable
4. **Computadora encendida** mientras uses el servicio

## 🚀 Pasos de Configuración

### 1. Instalar ngrok

**Windows:**
```bash
# Descarga desde https://ngrok.com/download
# O usando Chocolatey:
choco install ngrok

# O usando Scoop:
scoop install ngrok
```

**Verificar instalación:**
```bash
ngrok version
```

### 2. Crear cuenta en ngrok (gratis)

1. Ve a [ngrok.com](https://ngrok.com) y crea una cuenta
2. Obtén tu authtoken desde el dashboard
3. Configura el token:
```bash
ngrok config add-authtoken TU_TOKEN_AQUI
```

### 3. Configurar el Backend Local

#### 3.1. Instalar dependencias

```bash
# Activar entorno virtual (si lo tienes)
.\venv\Scripts\activate  # Windows
# o
source venv/bin/activate  # Linux/Mac

# Instalar dependencias
pip install -r requirements.txt
```

#### 3.2. Verificar que el backend funciona localmente

```bash
# Ejecutar el servidor
uvicorn api:app --host 0.0.0.0 --port 8000
```

Deberías ver:
```
INFO:     Uvicorn running on http://0.0.0.0:8000
```

Prueba en tu navegador: `http://localhost:8000/docs`

### 4. Exponer con ngrok

#### 4.1. Iniciar ngrok

En una **nueva terminal**, ejecuta:

```bash
ngrok http 8000
```

**Nota importante**: ngrok te dará una URL temporal que cambia cada vez que reinicias (en plan gratuito). Para una URL fija, necesitas el plan pago ($5/mes).

#### 4.2. Obtener la URL de ngrok

Verás algo como:
```
Forwarding   https://abc123.ngrok-free.app -> http://localhost:8000
```

Copia la URL `https://abc123.ngrok-free.app` (sin el `/` final)

### 5. Actualizar el Frontend

#### 5.1. Opción A: Hardcodear la URL de ngrok (temporal)

Edita `front_template/template/lib/api.ts`:

```typescript
const getBaseUrl = (): string => {
  // URL de ngrok (cambia cada vez que reinicias ngrok en plan gratuito)
  const NGROK_URL = 'https://TU_URL_NGROK.ngrok-free.app/api'
  
  // Production backend URL (Render)
  const PRODUCTION_URL = 'https://backsocial-83zt.onrender.com/api'
  
  // Local development URL
  const LOCAL_URL = 'http://localhost:8000/api'
  
  if (typeof window !== 'undefined') {
    const isLocalhost = window.location.hostname === 'localhost' || 
                        window.location.hostname === '127.0.0.1'
    
    // Si estás en producción (Vercel), usa ngrok
    // Si estás en localhost, usa LOCAL_URL
    return isLocalhost ? LOCAL_URL : NGROK_URL
  }
  
  return NGROK_URL
}
```

#### 5.2. Opción B: Usar variable de entorno (recomendado)

Crea un archivo `.env.local` en `front_template/template/`:

```env
NEXT_PUBLIC_API_URL=https://TU_URL_NGROK.ngrok-free.app/api
```

Y actualiza `api.ts`:

```typescript
const getBaseUrl = (): string => {
  // URL desde variable de entorno (ngrok)
  if (typeof window !== 'undefined' && process.env.NEXT_PUBLIC_API_URL) {
    return process.env.NEXT_PUBLIC_API_URL
  }
  
  // Fallback a localhost en desarrollo
  if (typeof window !== 'undefined') {
    const isLocalhost = window.location.hostname === 'localhost' || 
                        window.location.hostname === '127.0.0.1'
    return isLocalhost ? 'http://localhost:8000/api' : 'https://backsocial-83zt.onrender.com/api'
  }
  
  return 'https://backsocial-83zt.onrender.com/api'
}
```

### 6. Actualizar CORS en el Backend

Edita `api.py` para permitir la URL de ngrok:

```python
# CORS middleware
PRODUCTION_FRONTEND_URL = "https://frontsocial.vercel.app"
NGROK_URL = "https://TU_URL_NGROK.ngrok-free.app"  # Agrega tu URL de ngrok aquí

default_allowed_origins = [
    PRODUCTION_FRONTEND_URL,
    NGROK_URL,  # Agregar ngrok
    "http://localhost:3000",
    "http://localhost:3001",
    "http://127.0.0.1:3000",
]
```

## 🔄 Flujo de Trabajo Diario

### Iniciar el Backend:

1. **Terminal 1 - Backend:**
```bash
cd C:\Users\crist\OneDrive\Desktop\Test
.\venv\Scripts\activate
uvicorn api:app --host 0.0.0.0 --port 8000
```

2. **Terminal 2 - ngrok:**
```bash
ngrok http 8000
```

3. **Copiar la nueva URL de ngrok** (si cambió) y actualizar:
   - `front_template/template/lib/api.ts` (si usas hardcode)
   - O `.env.local` (si usas variables de entorno)
   - `api.py` (CORS)

### Mantener el Servicio Activo:

- ✅ Mantén ambas terminales abiertas
- ✅ No cierres la computadora (o usa "No dormir" en Windows)
- ✅ Si reinicias ngrok, actualiza la URL en el frontend

## ⚠️ Limitaciones de ngrok Gratuito

- ❌ **URL cambia** cada vez que reinicias ngrok
- ❌ **Límite de conexiones** simultáneas
- ❌ **Timeout** después de 2 horas de inactividad
- ❌ **Límite de ancho de banda** (40 MB/mes)

### Solución: Plan ngrok Pro ($5/mes)

- ✅ **URL fija** (dominio personalizado o subdominio ngrok)
- ✅ **Sin límites** de conexiones
- ✅ **Sin timeouts**
- ✅ **Más ancho de banda**

## 🔧 Scripts de Automatización (Opcional)

### Windows - Script para iniciar todo:

Crea `start-backend.bat`:

```batch
@echo off
echo Iniciando backend local con ngrok...

start cmd /k "cd /d %~dp0 && venv\Scripts\activate && uvicorn api:app --host 0.0.0.0 --port 8000"
timeout /t 3
start cmd /k "ngrok http 8000"

echo Backend iniciado en http://localhost:8000
echo ngrok iniciado - revisa la URL en la terminal de ngrok
pause
```

### Linux/Mac - Script para iniciar todo:

Crea `start-backend.sh`:

```bash
#!/bin/bash
echo "Iniciando backend local con ngrok..."

# Iniciar backend en background
cd "$(dirname "$0")"
source venv/bin/activate
uvicorn api:app --host 0.0.0.0 --port 8000 &
BACKEND_PID=$!

# Esperar un poco
sleep 3

# Iniciar ngrok
ngrok http 8000 &
NGROK_PID=$!

echo "Backend PID: $BACKEND_PID"
echo "ngrok PID: $NGROK_PID"
echo "Backend: http://localhost:8000"
echo "Revisa la URL de ngrok en la terminal"
```

## 🐛 Troubleshooting

### Error: "ngrok: command not found"
- Verifica que ngrok esté instalado: `ngrok version`
- Agrega ngrok al PATH de Windows

### Error: CORS en el frontend
- Verifica que la URL de ngrok esté en `api.py` en `allowed_origins`
- Reinicia el backend después de cambiar CORS

### Error: "Tunnel not found"
- Reinicia ngrok: `Ctrl+C` y luego `ngrok http 8000` de nuevo
- Actualiza la URL en el frontend

### El backend se detiene
- Verifica que Python esté corriendo
- Revisa los logs en la terminal del backend
- Asegúrate de que el puerto 8000 no esté ocupado

## 📊 Comparación: Render vs Local + ngrok

| Característica | Render Starter | Local + ngrok |
|---------------|----------------|---------------|
| **RAM** | 512 MB | Ilimitada (tu PC) |
| **Costo** | $7/mes | $0 (gratis) o $5/mes (ngrok Pro) |
| **URL fija** | ✅ Sí | ❌ No (gratis) / ✅ Sí (Pro) |
| **Disponibilidad** | 24/7 | Solo cuando PC está encendida |
| **Cold start** | ~30-60s | Instantáneo |
| **Control** | Limitado | Total |

## ✅ Recomendación

- **Desarrollo/Testing**: Usa local + ngrok (gratis)
- **Producción pequeña**: Render Starter ($7/mes)
- **Producción seria**: Local + ngrok Pro ($5/mes) o Render Standard

---

**¡Listo!** Ahora puedes ejecutar el backend en tu computadora y exponerlo con ngrok. 🎉
