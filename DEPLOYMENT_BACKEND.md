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
     ALLOWED_ORIGINS=https://tu-frontend.vercel.app,http://localhost:3000
     APIFY_TOKEN=tu_token_de_apify_aqui
     PYTHON_VERSION=3.11.0
     ```
   - ⚠️ **IMPORTANTE**: 
     - Reemplaza `tu-frontend.vercel.app` con la URL real de tu frontend (puedes actualizarlo después)
     - El `APIFY_TOKEN` es tu token real de Apify
     - Puedes dejar `http://localhost:3000` para desarrollo local

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

## 🔄 Paso 4: Actualizar CORS después de desplegar el frontend

Una vez que tengas la URL de tu frontend desplegado:

1. **Vuelve a Render Dashboard**
2. **Ve a tu servicio web**
3. **Environment Variables**
4. **Actualiza `ALLOWED_ORIGINS`** con la URL de tu frontend:
   ```
   ALLOWED_ORIGINS=https://tu-frontend.vercel.app,http://localhost:3000
   ```
5. **Render redeploy automáticamente** al detectar cambios en variables de entorno

## 📝 Notas Importantes

1. **Base de datos**: 
   - Render usa SQLite en el sistema de archivos
   - Los datos se mantienen incluso si el servicio se duerme
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
- SQLite se guarda en el sistema de archivos de Render
- Los datos deberían persistir entre deployments
- Si pierdes datos, puede ser porque Render recreó el servicio

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
