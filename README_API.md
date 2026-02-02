# 🚀 Migración a API REST + Frontend Next.js

Este proyecto ahora soporta dos modos de ejecución:
1. **Streamlit** (modo original) - `streamlit run app.py`
2. **API REST + Next.js** (nuevo) - Backend FastAPI + Frontend Next.js

## 📋 Estructura del Proyecto

```
proyecto/
├── backend/              # Código Python (existente)
│   ├── api.py           # API REST con FastAPI (NUEVO)
│   ├── app.py           # Streamlit app (original)
│   ├── scraper.py
│   ├── config.py
│   ├── db_utils.py
│   └── ...
│
└── front_template/       # Frontend Next.js
    └── template/
        ├── app/          # Páginas Next.js
        ├── components/   # Componentes React
        ├── lib/
        │   ├── api.ts    # Cliente API (NUEVO)
        │   └── mock-data.ts  # Mock data (original)
        └── ...
```

## 🔧 Instalación y Configuración

### 1. Backend (Python/FastAPI)

```bash
# Instalar dependencias
pip install -r requirements.txt

# Iniciar el servidor API
python api.py
# O con uvicorn directamente:
uvicorn api:app --reload --port 8000
```

El API estará disponible en: `http://localhost:8000`

### 2. Frontend (Next.js)

```bash
# Ir a la carpeta del template
cd front_template/template

# Instalar dependencias
npm install

# Configurar variables de entorno
cp .env.local.example .env.local
# Editar .env.local y configurar NEXT_PUBLIC_API_URL si es necesario

# Iniciar el servidor de desarrollo
npm run dev
```

El frontend estará disponible en: `http://localhost:3000`

## 📡 Endpoints de la API

### Perfiles
- `GET /api/profiles` - Obtener todos los perfiles
- `POST /api/profiles` - Crear un perfil
- `DELETE /api/profiles/{id}` - Eliminar un perfil

### Posts
- `GET /api/posts` - Obtener posts con filtros
  - Query params: `platform`, `profile_id`, `min_interactions`, `date_from`, `date_to`, `limit`, `offset`

### Comentarios
- `GET /api/comments` - Obtener comentarios con filtros
  - Query params: `platform`, `profile_id`, `post_id`, `sentiment`, `limit`, `offset`

### Análisis
- `POST /api/analysis/run` - Ejecutar análisis
  - Body: `{ "profile_ids": [1, 2], "force": false }`

### Estadísticas
- `GET /api/stats/sentiment` - Estadísticas de sentimiento
- `GET /api/stats/overview` - Estadísticas generales (KPIs)

### Configuración
- `GET /api/config` - Obtener toda la configuración
- `POST /api/config/apify-token` - Actualizar token de Apify
- `POST /api/config/actor-id` - Actualizar ID de actor

### Apify
- `GET /api/apify/usage` - Información de uso de Apify

### Health Check
- `GET /api/health` - Verificar estado del servidor

## 🔄 Migración del Frontend

El frontend ahora usa `lib/api.ts` en lugar de `lib/mock-data.ts`. 

Para actualizar una página:
1. Importar funciones de `@/lib/api` en lugar de `@/lib/mock-data`
2. Usar `useEffect` y `useState` para cargar datos
3. Manejar estados de loading, error, y success

Ejemplo:
```typescript
import { getPosts, getOverviewStats } from '@/lib/api'
import { useState, useEffect } from 'react'

export default function MyPage() {
  const [posts, setPosts] = useState([])
  const [loading, setLoading] = useState(true)
  
  useEffect(() => {
    async function loadData() {
      try {
        const response = await getPosts({ limit: 50 })
        setPosts(response.data)
      } catch (error) {
        console.error('Error loading posts:', error)
      } finally {
        setLoading(false)
      }
    }
    loadData()
  }, [])
  
  // ... resto del componente
}
```

## 🚀 Próximos Pasos

1. ✅ API REST creada
2. ✅ Cliente API en frontend creado
3. ⏳ Actualizar páginas del frontend para usar API real
4. ⏳ Agregar manejo de errores y loading states
5. ⏳ Testing y optimización

## 📝 Notas

- El backend usa la misma base de datos SQLite que Streamlit
- Los cambios en la configuración se reflejan en ambos modos
- El frontend puede funcionar independientemente del backend (usando mock data)
- CORS está configurado para `localhost:3000` (Next.js default)
