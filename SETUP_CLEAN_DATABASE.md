# 🗄️ Configurar Base de Datos Limpia

Esta guía te ayudará a crear una base de datos PostgreSQL limpia (sin datos) sin borrar la que ya tienes.

## 📋 Opciones

### Opción 1: Crear Nueva Base de Datos en Render (Recomendado)

1. **Ve a Render Dashboard** → "New" → "PostgreSQL"

2. **Configura la nueva base de datos:**
   - **Name**: `social-media-analytics-clean` (o el nombre que prefieras)
   - **Database**: `socialm_clean` (o el nombre que prefieras)
   - **User**: Se genera automáticamente
   - **Region**: Misma región que tu base de datos original
   - **Plan**: Free (1 GB)

3. **Copia la URL de conexión:**
   - Ve a la nueva base de datos en Render
   - Copia la "Internal Database URL" o "External Connection String"
   - Formato: `postgresql://user:password@host:port/database`

4. **Actualiza `db_utils.py`:**
   ```python
   PRODUCTION_DATABASE_URL_CLEAN = "postgresql://user:password@host:port/socialm_clean"
   ```

5. **Reinicia el backend** para que use la nueva base de datos

### Opción 2: Usar la Misma Base de Datos con Nombre Diferente

Si tienes acceso a PostgreSQL directamente, puedes crear una nueva base de datos en el mismo servidor:

1. **Conéctate a PostgreSQL:**
   ```bash
   psql "postgresql://socialm_user:oShfmZGuaVNQD9GKA0ha1pTyOmWdRYN9@dpg-d60mks63jp1c73a8vrtg-a/socialm"
   ```

2. **Crea una nueva base de datos:**
   ```sql
   CREATE DATABASE socialm_clean;
   ```

3. **Actualiza `db_utils.py`:**
   ```python
   PRODUCTION_DATABASE_URL_CLEAN = "postgresql://socialm_user:oShfmZGuaVNQD9GKA0ha1pTyOmWdRYN9@dpg-d60mks63jp1c73a8vrtg-a/socialm_clean"
   ```

### Opción 3: Usar SQLite Local (Solo para Desarrollo)

Si solo quieres probar localmente sin afectar la base de datos de producción:

1. **Comenta la conexión PostgreSQL en `db_utils.py`:**
   ```python
   # PRODUCTION_DATABASE_URL = PRODUCTION_DATABASE_URL_CLEAN or PRODUCTION_DATABASE_URL_ORIGINAL
   # DATABASE_URL = os.getenv("DATABASE_URL") or PRODUCTION_DATABASE_URL
   DATABASE_URL = None  # Esto forzará el uso de SQLite
   ```

2. **SQLite se creará automáticamente** en `social_media_analytics.db`

## 🔄 Cambiar Entre Bases de Datos

Para cambiar entre la base de datos original y la limpia:

1. **Usar BD limpia:**
   - Configura `PRODUCTION_DATABASE_URL_CLEAN` en `db_utils.py`
   - El código automáticamente usará la limpia

2. **Usar BD original:**
   - Pon `PRODUCTION_DATABASE_URL_CLEAN = None` en `db_utils.py`
   - El código automáticamente usará la original

## ✅ Verificar Qué Base de Datos se Está Usando

Revisa los logs al iniciar el backend:

```
✅ Using PostgreSQL database (production)
   Database: CLEAN database (new, empty)  ← BD limpia
   o
   Database: ORIGINAL database (with existing data)  ← BD original
```

## ⚠️ Notas Importantes

- **No se borran datos**: La base de datos original permanece intacta
- **Datos separados**: Cada base de datos tiene sus propios datos
- **Límite de almacenamiento**: Cada base de datos tiene 1 GB (si usas plan gratuito)
- **Costo**: Si creas una nueva BD en Render, cuenta como un servicio separado

## 🎯 Recomendación

Para desarrollo/testing: Usa **Opción 1** (nueva BD en Render) o **Opción 3** (SQLite local)

Para producción: Usa la base de datos original con los datos existentes

---

**¡Listo!** Ahora puedes trabajar con una base de datos limpia sin afectar tus datos existentes. 🎉
