# 🚀 Guía de Deployment - Backend (FastAPI)

Esta guía te ayudará a desplegar el backend en **Render**.

## 📋 Prerequisitos

1. Cuenta en [Render](https://render.com) (gratis disponible)
2. Cuenta en [GitHub](https://github.com) (gratis)
3. Token de Apify (obtén uno en [Apify Console](https://console.apify.com/account/integrations))

## 🔧 Paso 1: Preparar el Repositorio en GitHub

1. **Inicializa Git (si no está inicializado)**
```bash
git init
git add .
git commit -m "Initial commit - Backend API"
```

2. **Crea un repositorio en GitHub** y conecta tu proyecto:
```bash
git remote add origin https://github.com/tu-usuario/tu-repositorio-backend.git
git branch -M main
git push -u origin main
```

⚠️ **IMPORTANTE**: Asegúrate de que `front_template/` esté en `.gitignore` (ya está configurado)

## 🖥️ Paso 2: Desplegar en Render

1. **Ve a [Render Dashboard](https://dashboard.render.com)**

2. **Crea un nuevo Web Service**
   - Click en "New" → "Web Service"
   - Conecta tu repositorio de GitHub
   - Selecciona el repositorio del backend

3. **Configura el servicio:**
   - **Name**: `social-media-analytics-api` (o el nombre que prefieras)
   - **Environment**: `Python 3`
   - **Build Command**: `pip install -r requirements.txt`
   - **Start Command**: `uvicorn api:app --host 0.0.0.0 --port $PORT`

4. **Configura las Variables de Entorno:**
   - Click en "Environment" tab
   - Agrega las siguientes variables:
     ```
     ALLOWED_ORIGINS=http://localhost:3000
     PYTHON_VERSION=3.11.0 (opcional)
     ```
   - ⚠️ **IMPORTANTE**: 
     - **NO agregues `APIFY_TOKEN` aquí** - El token se configura desde la interfaz web en la página de Configuración
     - Reemplaza `http://localhost:3000` con la URL de tu frontend después de desplegarlo en Vercel
     - Puedes actualizar `ALLOWED_ORIGINS` después con la URL de Vercel

5. **Guarda y despliega**
   - Render comenzará a construir y desplegar tu aplicación
   - Anota la URL que te da Render (ej: `https://social-media-analytics-api.onrender.com`)

## ✅ Paso 3: Verificar el Deployment

1. **Abre la URL de Render en el navegador**
   - Deberías ver la documentación de FastAPI (Swagger UI)
   - Ejemplo: `https://tu-api.onrender.com/docs`

2. **Prueba un endpoint**
   - Ve a `https://tu-api.onrender.com/api/profiles`
   - Deberías ver una respuesta JSON (probablemente un array vacío `[]`)

3. **Verifica los logs**
   - En Render Dashboard → Logs
   - Deberías ver que el servidor está corriendo sin errores

## 🔄 Paso 4: Configurar el Token de Apify

**IMPORTANTE**: El token de Apify NO se configura en Render, sino desde la interfaz web:

1. **Despliega el frontend en Vercel** (verás cómo en el siguiente paso)
2. **Abre tu aplicación en Vercel**
3. **Ve a la página "Configuración"** (⚙️)
4. **Pega tu token de Apify** en el campo correspondiente
5. **Guarda** - El token se guardará en la base de datos

Esto permite cambiar el token fácilmente cuando se acabe el plan gratuito, sin necesidad de tocar Render.

## 🔄 Paso 5: Actualizar CORS después de desplegar el frontend

Una vez que tengas la URL de tu frontend desplegado:

1. **Vuelve a Render Dashboard**
2. **Ve a tu servicio web**
3. **Environment Variables**
4. **Actualiza `ALLOWED_ORIGINS`** con la URL de tu frontend:
   ```
   ALLOWED_ORIGINS=https://tu-frontend.vercel.app,http://localhost:3000
   ```
5. **Render redeploy automáticamente** al detectar cambios en variables de entorno

## 🗄️ Paso 2.5: Configurar Base de Datos PostgreSQL (IMPORTANTE)

**⚠️ CRÍTICO**: La conexión a PostgreSQL está hardcodeada en el código para producción.

**Base de datos configurada:**
- **URL**: Hardcodeada en `db_utils.py`
- **Database**: `socialm`
- **Plan**: Free (1 GB de almacenamiento máximo)
- **⚠️ Límite**: El plan gratuito tiene 1 GB de almacenamiento. Monitorea el uso en Render Dashboard.

**Nota sobre la conexión:**
- El código usa la conexión PostgreSQL hardcodeada en producción
- Si existe `DATABASE_URL` en variables de entorno, se usa esa (tiene prioridad)
- Si no existe `DATABASE_URL`, se usa la conexión hardcodeada
- En desarrollo local (sin PostgreSQL), usa SQLite automáticamente

**Monitoreo de almacenamiento:**
- Ve a tu base de datos PostgreSQL en Render Dashboard
- Revisa la sección "Storage" para ver el uso actual
- El plan gratuito tiene 1 GB máximo
- Si necesitas más espacio, considera actualizar a un plan pago

## 📝 Notas Importantes

1. **Base de datos**: 
   - **Producción (Render)**: Usa PostgreSQL (persistente, no se pierde al reiniciar)
   - **Desarrollo local**: Usa SQLite automáticamente si no hay `DATABASE_URL`
   - ⚠️ En el plan gratuito, si el servicio se duerme, puede tardar ~30-60 segundos en iniciar (cold start)

2. **Cold Start**: 
   - En el plan gratuito, el servicio se duerme después de 15 min de inactividad
   - El primer request después de dormirse puede tardar 30-60 segundos

3. **Límites del plan gratuito**:
   - 750 horas/mes
   - Servicio se duerme después de 15 min de inactividad
   - Ancho de banda limitado

4. **Actualizaciones**: 
   - Cada push a `main` desplegará automáticamente (si tienes auto-deploy habilitado)
   - O puedes hacer deploy manual desde Render Dashboard

5. **Variables de entorno**: 
   - ⚠️ **NUNCA** subas tokens o credenciales al código
   - Siempre usa variables de entorno en Render Dashboard

## 🚨 Problemas Comunes y Soluciones

### Problema 1: El servicio excede su límite de memoria RAM

**Síntomas:**
- Recibes un email de Render: "Ran out of memory (used over 512MB)"
- El servicio se reinicia automáticamente
- Error: "Instance failed: Ran out of memory"

**Causa:**
- El plan **Free** de Render tiene solo **512 MB de RAM**
- El modelo de HuggingFace (`cardiffnlp/twitter-xlm-roberta-base-sentiment`) es grande y consume mucha memoria
- Aunque el modelo se carga de forma "lazy", cuando se carga consume ~300-500 MB de RAM
- Con el servidor base + modelo + procesamiento, se supera el límite de 512 MB

**Soluciones:**

1. **Upgrade a plan Starter (RECOMENDADO):**
   - El plan **Starter** ($7/mes) tiene **512 MB - 1 GB de RAM**
   - Esto es suficiente para el modelo y el procesamiento
   - Ya cambiaste a Starter según los logs, esto debería solucionar el problema

2. **Optimizaciones implementadas:**
   - ✅ Modelo se carga de forma "lazy" (solo cuando se necesita)
   - ✅ Usa CPU en lugar de GPU (ahorra memoria)
   - ✅ Procesa comentarios uno por uno (batch_size=1)
   - ✅ Intenta usar float16 para reducir memoria (si el modelo lo soporta)
   - ✅ Limpieza de memoria periódica con garbage collection

3. **Si aún tienes problemas de memoria:**
   - Considera usar un modelo más ligero (configurable en settings)
   - Procesa menos comentarios por vez
   - Actualiza a un plan con más RAM (Starter Plus, Standard, etc.)

**Nota importante:**
- **RAM (memoria)** ≠ **Almacenamiento de BD**
- El problema es de **RAM** (memoria temporal para ejecutar el código)
- El almacenamiento de PostgreSQL (1 GB) es diferente y está bien

### Problema 2: Los datos se borran al reiniciar

**Causa:** Estás usando SQLite en lugar de PostgreSQL

**Solución:**
1. Verifica que `DATABASE_URL` esté configurada en Render Dashboard
2. Revisa los logs al iniciar el servicio:
   - ✅ Debe decir: `Using PostgreSQL database (production)`
   - ❌ NO debe decir: `Using SQLite database (development/local)`
3. Si ves el mensaje de SQLite, configura PostgreSQL siguiendo los pasos arriba

### Verificar la configuración de la base de datos

En los logs de Render, al iniciar el servicio deberías ver:

```
INFO:db_utils:✅ Using PostgreSQL database (production)
INFO:db_utils:   Database: socialm (1 GB storage limit on free plan)
INFO:db_utils:   Using hardcoded production database connection
INFO:api:Database initialized successfully
```

Si ves esto, está correcto. Si ves:

```
WARNING:db_utils:⚠️  Using SQLite database (development/local)
WARNING:db_utils:   ⚠️  WARNING: SQLite data will be LOST on server restart!
```

Entonces hay un problema con la conexión PostgreSQL (psycopg2-binary no está instalado o hay un error de conexión).

**Monitoreo de almacenamiento:**
- El plan gratuito tiene **1 GB máximo** de almacenamiento
- Monitorea el uso en Render Dashboard → PostgreSQL → Storage
- Si necesitas más espacio, actualiza a un plan pago

## 🐛 Troubleshooting

### Backend no responde
- Verifica que el `startCommand` sea correcto: `uvicorn api:app --host 0.0.0.0 --port $PORT`
- Revisa los logs en Render Dashboard → Logs
- Asegúrate de que el puerto sea `$PORT` (variable de Render, no un número fijo)

### Error al instalar dependencias
- Verifica que `requirements.txt` esté en la raíz del repositorio
- Revisa los logs de build en Render
- Asegúrate de que todas las dependencias estén listadas

### CORS errors
- Verifica que `ALLOWED_ORIGINS` en Render incluya tu URL de frontend
- Asegúrate de incluir `https://` en la URL
- No incluyas la barra final `/` en las URLs
- Render redeploy automáticamente al cambiar variables de entorno

### Base de datos no persiste
- **IMPORTANTE**: Asegúrate de haber creado una base de datos PostgreSQL en Render
- Verifica que `DATABASE_URL` esté configurada en las variables de entorno del web service
- Si usas SQLite (solo desarrollo local), los datos pueden perderse al reiniciar el servicio
- PostgreSQL es persistente y los datos se mantienen incluso si el servicio se reinicia

### El servicio está "dormido"
- Es normal en el plan gratuito después de 15 min de inactividad
- El primer request después de dormirse puede tardar 30-60 segundos
- Considera usar un servicio de "ping" para mantener el servicio activo (opcional)

## 📚 Recursos

- [Render Documentation](https://render.com/docs)
- [FastAPI Deployment](https://fastapi.tiangolo.com/deployment/)
- [Uvicorn Documentation](https://www.uvicorn.org/)

## 🔐 Seguridad

- ✅ **Nunca subas tokens o credenciales a GitHub**
- ✅ Usa variables de entorno para información sensible
- ✅ El archivo `.gitignore` ya está configurado para excluir archivos sensibles
- ✅ Los tokens se configuran desde Render Dashboard

---

**¡Listo! Tu backend debería estar funcionando en Render.** 🎉
