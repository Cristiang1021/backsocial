# Desplegar el backend en Vercel

Este backend (FastAPI) está preparado para Vercel: solo API, sin Streamlit, sin modelo pesado de sentimiento en el build (se usa análisis por keywords en Vercel para ahorrar memoria).

## Pasos

1. **Conectar el repo** en [Vercel](https://vercel.com) (solo esta carpeta del backend, o monorepo con root aquí).

2. **Variables de entorno** (en Project Settings → Environment Variables):
   - **Turso (SQLite en la nube)** – recomendado para persistencia sin Postgres:
     - `TURSO_DATABASE_URL`: URL de la BD en Turso (ej. `libsql://scra-cristiang1046.aws-us-east-1.turso.io`).
     - `TURSO_AUTH_TOKEN`: token de acceso (Turso Cloud → tu base de datos → **Create Token**).
   - **Postgres** (alternativa): `DATABASE_URL` con la cadena de conexión Postgres.
   - `ALLOWED_ORIGINS`: opcional; si no se define, se permiten `https://frontsocial.vercel.app` y `http://localhost:3000`. Si tu front está en otra URL, añádela aquí (separada por comas).
   - `DB_PATH`: solo si usas SQLite local en Vercel (no recomendado; los datos no persisten). Con Turso o Postgres no hace falta.
   - Tokens y configuración que use tu front (Apify, etc.) según tu flujo.

3. **Build**: Vercel instalará dependencias con `pip install -r requirements.txt`. La app se expone con el entry point `api:app` (configurado en `pyproject.toml`).

4. **Frontend**: En tu proyecto `front_template` (o el que tengas en Vercel), configura la URL base de la API apuntando a la URL que te asigne Vercel para este backend (ej. `https://tu-proyecto.vercel.app`).

## Notas

- **Sentimiento**: En este setup no se instalan `transformers` ni `torch` para mantener el despliegue ligero. El análisis usa solo palabras clave y, cuando no hay coincidencia, devuelve NEUTRAL. Si más adelante quieres el modelo HuggingFace, despliega en Render/VPS y descomenta en `requirements.txt` las líneas de `transformers` y `torch`.
- **ESLint**: Este proyecto es solo backend (Python); no hay ESLint aquí. El front (front_template) se despliega por separado.
