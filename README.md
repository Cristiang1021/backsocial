# 📊 Social Media Analytics Dashboard - Backend API

API REST (FastAPI) para análisis de redes sociales (Instagram, TikTok, Facebook) con scraping automatizado, análisis de sentimiento y persistencia de datos.

## 🌐 Deployment

Este backend está listo para desplegarse en **Render**.

📖 **Ver [DEPLOYMENT_BACKEND.md](./DEPLOYMENT_BACKEND.md) para instrucciones completas de deployment**

## 🚀 Características

- **API REST con FastAPI**: Endpoints para perfiles, posts, comentarios, análisis y configuración
- **Scraping con Apify**: Integración con actores de Apify para extraer posts y comentarios
- **Análisis de Sentimiento Híbrido**: Combina modelos de HuggingFace con reglas basadas en palabras clave
- **Persistencia SQLite**: Todos los datos se guardan en base de datos
- **CORS Configurado**: Listo para conectar con frontend en producción
- **Multi-plataforma**: Soporte para Instagram, TikTok y Facebook

## 📋 Requisitos

- Python 3.8 o superior
- Token de API de Apify (obtén uno en [Apify Console](https://console.apify.com/account/integrations))
- ~2GB de espacio en disco (para modelos de HuggingFace)

## 🔧 Instalación Local

1. **Clona o descarga el proyecto**

2. **Crea un entorno virtual (recomendado)**
```bash
python -m venv venv
source venv/bin/activate  # En Windows: venv\Scripts\activate
```

3. **Instala las dependencias**
```bash
pip install -r requirements.txt
```

4. **Inicializa la base de datos**
La base de datos se creará automáticamente al ejecutar la aplicación por primera vez.

## 🎯 Uso Local

### Ejecutar el servidor

```bash
uvicorn api:app --reload
```

El servidor estará disponible en `http://localhost:8000`

### Documentación de la API

Una vez que el servidor esté corriendo, puedes acceder a:
- **Swagger UI**: `http://localhost:8000/docs`
- **ReDoc**: `http://localhost:8000/redoc`

### Variables de Entorno (Opcional)

Crea un archivo `.env` en la raíz del proyecto:

```env
ALLOWED_ORIGINS=http://localhost:3000,http://127.0.0.1:3000
APIFY_TOKEN=tu_token_aqui
```

O configura el token desde la API después de iniciar el servidor.

## 📁 Estructura del Proyecto

```
.
├── api.py              # Aplicación FastAPI principal
├── config.py           # Gestión de configuraciones
├── db_utils.py         # Utilidades de base de datos SQLite
├── scraper.py          # Módulo de scraping con Apify
├── analyzer.py         # Análisis de sentimiento
├── utils.py            # Funciones auxiliares
├── requirements.txt    # Dependencias
├── render.yaml         # Configuración para Render
├── Procfile            # Comando de inicio para Render
├── runtime.txt         # Versión de Python
├── README.md           # Este archivo
└── DEPLOYMENT_BACKEND.md  # Guía de deployment
```

## 🔌 Endpoints Principales

### Perfiles
- `GET /api/profiles` - Obtener todos los perfiles
- `POST /api/profiles` - Crear un nuevo perfil
- `DELETE /api/profiles/{profile_id}` - Eliminar un perfil

### Posts
- `GET /api/posts` - Obtener posts con filtros (plataforma, fecha, etc.)

### Comentarios
- `GET /api/comments` - Obtener comentarios con filtros

### Análisis
- `POST /api/analyze` - Ejecutar análisis de perfiles

### Estadísticas
- `GET /api/stats/overview` - Estadísticas generales
- `GET /api/stats/sentiment` - Estadísticas de sentimiento

### Configuración
- `GET /api/config` - Obtener toda la configuración
- `PUT /api/config/apify-token` - Actualizar token de Apify
- `PUT /api/config/actor-id` - Actualizar ID de actor

Ver documentación completa en `/docs` cuando el servidor esté corriendo.

## ⚙️ Configuraciones Disponibles

Todas estas configuraciones se pueden editar desde la API:

- **Token de Apify**: Token de API para acceder a Apify
- **Modelo de HuggingFace**: Modelo para análisis de sentimiento (default: `cardiffnlp/twitter-xlm-roberta-base-sentiment`)
- **Palabras Clave Positivas/Negativas**: Listas editables de palabras para reglas de sentimiento
- **IDs de Actores**: IDs de los actores de Apify para cada plataforma y tipo (posts/comments)
- **Límites por Defecto**: Límite de posts y comentarios a scrapear

## 🔍 Actores de Apify por Defecto

- **Instagram Posts**: `shu8hvrXbJbY3Eb9W`
- **Instagram Comments**: `instagram-comment-scraper`
- **TikTok Posts**: `GdWCkxBtKWOsKjdch`
- **TikTok Comments**: `tiktok-comments-scraper`
- **Facebook Posts**: `apify/facebook-posts-scraper` (actor oficial)
- **Facebook Comments**: `us5srxAYnsrkgUv2v` (`apify/facebook-comments-scraper` - actor oficial)

**Nota**: Estos IDs pueden cambiar. Verifica en [Apify Store](https://apify.com/store) los actores más actuales.

## 📊 Análisis de Sentimiento

El sistema usa un enfoque híbrido:

1. **Reglas de Palabras Clave** (prioridad alta):
   - Si el comentario contiene una palabra positiva → `POSITIVE` (confianza: 0.9)
   - Si contiene una palabra negativa → `NEGATIVE` (confianza: 0.9)

2. **Modelo de HuggingFace** (si no hay match de keywords):
   - Usa el modelo configurado para analizar el sentimiento
   - Mapea las etiquetas del modelo a POSITIVE/NEGATIVE/NEUTRAL

## 🛠️ Solución de Problemas

### Error: "Token de Apify no configurado"
- Configura el token usando `PUT /api/config/apify-token`
- O crea un archivo `.env` con `APIFY_TOKEN=tu_token`

### Error: "Invalid Apify token"
- Verifica que el token sea correcto en [Apify Console](https://console.apify.com/account/integrations)
- Asegúrate de que el token tenga permisos para ejecutar actores

### Error al cargar modelo de HuggingFace
- El sistema intentará usar un modelo de respaldo
- Verifica tu conexión a internet (los modelos se descargan la primera vez)
- Si persiste, cambia el modelo usando la API

### CORS errors
- Verifica que `ALLOWED_ORIGINS` incluya la URL de tu frontend
- En producción, configura `ALLOWED_ORIGINS` en Render con tu URL de frontend

## 🔒 Seguridad

- ✅ **Nunca subas tokens o credenciales a GitHub**
- ✅ Usa variables de entorno para información sensible
- ✅ El archivo `.gitignore` está configurado para excluir archivos sensibles
- ✅ En producción, configura los tokens desde Render Dashboard

## 📄 Licencia

Este proyecto es de código abierto y está disponible para uso personal y comercial.

## 🤝 Contribuciones

Las contribuciones son bienvenidas. Por favor:
1. Fork el proyecto
2. Crea una rama para tu feature
3. Commit tus cambios
4. Push a la rama
5. Abre un Pull Request

---

**¡Disfruta analizando tus redes sociales! 📊✨**
