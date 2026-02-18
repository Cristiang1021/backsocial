"""
Database utilities for SQLite, PostgreSQL and Turso (libSQL) operations.
Handles initialization, schema creation, and common database operations.
- PostgreSQL si DATABASE_URL está definida.
- Turso (SQLite en la nube) si TURSO_DATABASE_URL y TURSO_AUTH_TOKEN están definidas.
- SQLite local en caso contrario.
"""
import json
import os
import csv
import io
from typing import Any, Dict, List, Optional, Tuple
from datetime import datetime
from pathlib import Path

# Try to import PostgreSQL adapter
try:
    import psycopg2
    from psycopg2.extras import RealDictCursor
    PSYCOPG2_AVAILABLE = True
except ImportError:
    PSYCOPG2_AVAILABLE = False

# Try to import SQLite (always available in Python stdlib)
try:
    import sqlite3
    SQLITE_AVAILABLE = True
except ImportError:
    SQLITE_AVAILABLE = False

# Try to import Turso/libSQL client (pip install libsql-client)
try:
    import libsql_client
    LIBSQL_CLIENT_AVAILABLE = True
except ImportError:
    LIBSQL_CLIENT_AVAILABLE = False

# Database configuration
_THIS_DIR = Path(__file__).resolve().parent
DB_PATH = Path(os.getenv("DB_PATH", str(_THIS_DIR / "social_media_analytics.db")))

# Cadenas de conexión por variable de entorno
DATABASE_URL = os.getenv("DATABASE_URL")  # Postgres: postgresql://...
TURSO_DATABASE_URL = os.getenv("TURSO_DATABASE_URL")  # Turso: libsql://nombre-usuario.region.turso.io
TURSO_AUTH_TOKEN = os.getenv("TURSO_AUTH_TOKEN")  # Token desde Turso Cloud → Create Token

# Orden de prioridad: Postgres > Turso > SQLite
USE_POSTGRES = PSYCOPG2_AVAILABLE and (DATABASE_URL or "").strip() != ""
USE_TURSO = (
    LIBSQL_CLIENT_AVAILABLE
    and (TURSO_DATABASE_URL or "").strip() != ""
    and (TURSO_AUTH_TOKEN or "").strip() != ""
    and not USE_POSTGRES
)
USE_SQLITE = not USE_POSTGRES and not USE_TURSO and SQLITE_AVAILABLE

import logging
logger = logging.getLogger(__name__)

if USE_POSTGRES:
    logger.info("✅ Using PostgreSQL database (DATABASE_URL)")
elif USE_TURSO:
    logger.info("✅ Using Turso database (TURSO_DATABASE_URL + TURSO_AUTH_TOKEN)")
    logger.info("   URL: %s", (TURSO_DATABASE_URL or "").split("?")[0])
else:
    logger.info("✅ Using SQLite database (local)")
    logger.info("   Database file: %s", DB_PATH.absolute())

if not (USE_POSTGRES or USE_TURSO or USE_SQLITE):
    raise RuntimeError(
        "No database configured. Set DATABASE_URL (Postgres), or TURSO_DATABASE_URL + TURSO_AUTH_TOKEN (Turso), "
        "or use SQLite locally. For Turso install: pip install libsql-client"
    )


# --- Turso: adaptador connection/cursor compatible con el resto del código ---
class _TursoCursorWrapper:
    """Cursor que imita sqlite3.Cursor usando el cliente libsql."""
    def __init__(self, conn_wrapper: "_TursoConnectionWrapper"):
        self._conn = conn_wrapper
        self._last_result = None

    def execute(self, query: str, params: Tuple = ()) -> None:
        args = list(params) if params else None
        self._last_result = self._conn._client.execute(query, args)

    def fetchall(self):
        if not self._last_result:
            return []
        return [row.asdict() for row in self._last_result.rows]

    def fetchone(self):
        if not self._last_result or not self._last_result.rows:
            return None
        return self._last_result.rows[0].asdict()

    @property
    def lastrowid(self) -> Optional[int]:
        if not self._last_result:
            return None
        return self._last_result.last_insert_rowid

    @property
    def rowcount(self) -> int:
        if not self._last_result:
            return 0
        return self._last_result.rows_affected or 0

    def close(self) -> None:
        pass


class _TursoConnectionWrapper:
    """Conexión que imita sqlite3/psycopg2 para usar Turso vía libsql_client."""
    def __init__(self):
        self._client = libsql_client.create_client_sync(
            TURSO_DATABASE_URL.strip(),
            auth_token=TURSO_AUTH_TOKEN.strip(),
        )

    def cursor(self):
        return _TursoCursorWrapper(self)

    def commit(self) -> None:
        pass  # Turso ejecuta cada sentencia de forma inmediata

    def rollback(self) -> None:
        pass

    def close(self) -> None:
        try:
            self._client.close()
        except Exception:
            pass


def get_connection():
    """Get a database connection (PostgreSQL, Turso or SQLite)."""
    if USE_POSTGRES:
        return psycopg2.connect(DATABASE_URL)
    if USE_TURSO:
        return _TursoConnectionWrapper()
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def _execute_query(query: str, params: Tuple = (), fetch: bool = True):
    """Execute a query and return results. Handles both PostgreSQL and SQLite."""
    conn = get_connection()
    cursor = conn.cursor()
    
    try:
        # Convert SQLite-style ? placeholders to PostgreSQL %s if needed
        if USE_POSTGRES:
            query = query.replace("?", "%s")
        
        cursor.execute(query, params)
        
        if fetch:
            if USE_POSTGRES:
                # Use RealDictCursor for PostgreSQL to get dict-like rows
                cursor.close()
                dict_cursor = conn.cursor(cursor_factory=RealDictCursor)
                dict_cursor.execute(query, params)
                rows = dict_cursor.fetchall()
                result = [dict(row) for row in rows]
                dict_cursor.close()
            else:
                # SQLite
                rows = cursor.fetchall()
                result = [dict(row) for row in rows]
        else:
            result = None
        
        conn.commit()
        return result
    except Exception as e:
        conn.rollback()
        raise
    finally:
        conn.close()


def _execute_update(query: str, params: Tuple = ()):
    """Execute an update/insert query and return lastrowid."""
    conn = get_connection()
    cursor = conn.cursor()
    
    try:
        # Convert SQLite-style ? placeholders to PostgreSQL %s if needed
        if USE_POSTGRES:
            query = query.replace("?", "%s")
            # PostgreSQL uses ON CONFLICT instead of INSERT OR REPLACE
            query = query.replace("INSERT OR REPLACE", "INSERT")
            query = query.replace("INSERT INTO", "INSERT INTO")
        
        cursor.execute(query, params)
        
        if USE_POSTGRES:
            conn.commit()
            # For PostgreSQL, get the last inserted ID differently
            if "INSERT" in query.upper():
                cursor.execute("SELECT LASTVAL()")
                lastrowid = cursor.fetchone()[0]
            else:
                lastrowid = cursor.rowcount
        else:
            lastrowid = cursor.lastrowid
            conn.commit()
        
        return lastrowid
    except Exception as e:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_database() -> None:
    """Initialize database with all required tables."""
    conn = get_connection()
    cursor = conn.cursor()
    
    try:
        # Config table: key-value store for all settings
        if USE_POSTGRES:
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS config (
                    key VARCHAR(255) PRIMARY KEY,
                    value TEXT NOT NULL
                )
            """)
        else:
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS config (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL
                )
            """)
        
        # Profiles table: stores monitored profiles
        if USE_POSTGRES:
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS profiles (
                    id SERIAL PRIMARY KEY,
                    platform VARCHAR(50) NOT NULL,
                    username_or_url VARCHAR(500) NOT NULL,
                    display_name VARCHAR(500),
                    last_analyzed TIMESTAMP,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(platform, username_or_url)
                )
            """)
        else:
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS profiles (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    platform TEXT NOT NULL,
                    username_or_url TEXT NOT NULL,
                    display_name TEXT,
                    last_analyzed DATETIME,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(platform, username_or_url)
                )
            """)
        
        # Posts table: stores scraped posts
        if USE_POSTGRES:
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS posts (
                    id SERIAL PRIMARY KEY,
                    profile_id INTEGER NOT NULL,
                    platform VARCHAR(50) NOT NULL,
                    post_id VARCHAR(500) NOT NULL,
                    url TEXT,
                    text TEXT,
                    likes INTEGER DEFAULT 0,
                    comments_count INTEGER DEFAULT 0,
                    shares INTEGER DEFAULT 0,
                    views INTEGER DEFAULT 0,
                    interactions_total INTEGER DEFAULT 0,
                    posted_at TIMESTAMP,
                    scraped_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (profile_id) REFERENCES profiles(id) ON DELETE CASCADE,
                    UNIQUE(platform, post_id)
                )
            """)
        else:
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS posts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    profile_id INTEGER NOT NULL,
                    platform TEXT NOT NULL,
                    post_id TEXT NOT NULL,
                    url TEXT,
                    text TEXT,
                    likes INTEGER DEFAULT 0,
                    comments_count INTEGER DEFAULT 0,
                    shares INTEGER DEFAULT 0,
                    views INTEGER DEFAULT 0,
                    interactions_total INTEGER DEFAULT 0,
                    posted_at DATETIME,
                    scraped_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (profile_id) REFERENCES profiles(id),
                    UNIQUE(platform, post_id)
                )
            """)
        
        # Comments table: stores comments with sentiment analysis
        if USE_POSTGRES:
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS comments (
                    id SERIAL PRIMARY KEY,
                    post_id INTEGER NOT NULL,
                    comment_id VARCHAR(500) NOT NULL,
                    text TEXT,
                    author VARCHAR(500),
                    likes INTEGER DEFAULT 0,
                    sentiment_label VARCHAR(50),
                    sentiment_score REAL,
                    sentiment_method VARCHAR(100),
                    posted_at TIMESTAMP,
                    scraped_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (post_id) REFERENCES posts(id) ON DELETE CASCADE,
                    UNIQUE(post_id, comment_id)
                )
            """)
        else:
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS comments (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    post_id INTEGER NOT NULL,
                    comment_id TEXT NOT NULL,
                    text TEXT,
                    author TEXT,
                    likes INTEGER DEFAULT 0,
                    sentiment_label TEXT,
                    sentiment_score REAL,
                    sentiment_method TEXT,
                    posted_at DATETIME,
                    scraped_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (post_id) REFERENCES posts(id),
                    UNIQUE(post_id, comment_id)
                )
            """)
        
        # Create indexes for better performance
        indexes = [
            ("idx_posts_profile", "posts(profile_id)"),
            ("idx_posts_platform", "posts(platform)"),
            ("idx_comments_post", "comments(post_id)"),
            ("idx_comments_sentiment", "comments(sentiment_label)"),
        ]
        
        for idx_name, idx_def in indexes:
            try:
                cursor.execute(f"CREATE INDEX IF NOT EXISTS {idx_name} ON {idx_def}")
            except Exception as e:
                # Index might already exist, ignore
                pass
        
        # Migración: columna apify_token_key en profiles (qué API key usar: facebook_1, facebook_2, instagram, tiktok)
        try:
            if USE_POSTGRES:
                cursor.execute("ALTER TABLE profiles ADD COLUMN IF NOT EXISTS apify_token_key VARCHAR(50)")
            else:
                cursor.execute("ALTER TABLE profiles ADD COLUMN apify_token_key TEXT")
        except Exception as e:
            if "duplicate column" in str(e).lower() or "already exists" in str(e).lower():
                pass
            else:
                raise
        
        conn.commit()
    except Exception as e:
        conn.rollback()
        raise
    finally:
        conn.close()


def get_config(key: str, default: Any = None) -> Any:
    """Get a configuration value from the database."""
    conn = get_connection()
    cursor = conn.cursor()
    
    try:
        if USE_POSTGRES:
            cursor.execute("SELECT value FROM config WHERE key = %s", (key,))
        else:
            cursor.execute("SELECT value FROM config WHERE key = ?", (key,))
        row = cursor.fetchone()
        
        if row:
            try:
                return json.loads(row[0])
            except json.JSONDecodeError:
                return row[0]
        return default
    finally:
        conn.close()


def set_config(key: str, value: Any) -> None:
    """Set a configuration value in the database."""
    conn = get_connection()
    cursor = conn.cursor()
    
    try:
        if isinstance(value, (dict, list)):
            value = json.dumps(value)
        else:
            value = str(value)
        
        if USE_POSTGRES:
            cursor.execute(
                "INSERT INTO config (key, value) VALUES (%s, %s) ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value",
                (key, value)
            )
        else:
            cursor.execute(
                "INSERT OR REPLACE INTO config (key, value) VALUES (?, ?)",
                (key, value)
            )
        
        conn.commit()
    finally:
        conn.close()


def get_all_profiles() -> List[Dict[str, Any]]:
    """Get all profiles from the database."""
    query = """
        SELECT id, platform, username_or_url, display_name, last_analyzed, created_at, apify_token_key
        FROM profiles
        ORDER BY platform, username_or_url
    """
    rows = _execute_query(query)
    # Asegurar que apify_token_key existe (BD antiguas pueden no tener la columna en el SELECT)
    for r in rows:
        if "apify_token_key" not in r:
            r["apify_token_key"] = None
    return rows


def get_profile_by_id(profile_id: int) -> Optional[Dict[str, Any]]:
    """Get a single profile by ID."""
    conn = get_connection()
    cursor = conn.cursor()
    try:
        if USE_POSTGRES:
            cursor = conn.cursor(cursor_factory=RealDictCursor)
            cursor.execute(
                "SELECT id, platform, username_or_url, display_name, last_analyzed, created_at, apify_token_key FROM profiles WHERE id = %s",
                (profile_id,)
            )
        else:
            cursor.execute(
                "SELECT id, platform, username_or_url, display_name, last_analyzed, created_at, apify_token_key FROM profiles WHERE id = ?",
                (profile_id,)
            )
        row = cursor.fetchone()
        if not row:
            return None
        if USE_POSTGRES:
            d = dict(row)
        else:
            d = dict(zip([c[0] for c in cursor.description], row))
        if "apify_token_key" not in d:
            d["apify_token_key"] = None
        return d
    finally:
        conn.close()


def add_profile(platform: str, username_or_url: str, display_name: Optional[str] = None) -> Optional[int]:
    """Add a new profile to the database. Returns the profile ID."""
    conn = get_connection()
    cursor = conn.cursor()
    
    try:
        if USE_POSTGRES:
            cursor.execute("""
                INSERT INTO profiles (platform, username_or_url, display_name)
                VALUES (%s, %s, %s)
                ON CONFLICT (platform, username_or_url) DO NOTHING
                RETURNING id
            """, (platform, username_or_url, display_name or username_or_url))
            result = cursor.fetchone()
            if result:
                profile_id = result[0]
            else:
                # Profile already exists, get its ID
                cursor.execute("""
                    SELECT id FROM profiles 
                    WHERE platform = %s AND username_or_url = %s
                """, (platform, username_or_url))
                row = cursor.fetchone()
                profile_id = row[0] if row else None
        else:
            # SQLite: Check if profile exists first, then INSERT or get existing ID
            cursor.execute("""
                SELECT id FROM profiles 
                WHERE platform = ? AND username_or_url = ?
            """, (platform, username_or_url))
            existing = cursor.fetchone()
            
            if existing:
                # Profile already exists, return its ID
                profile_id = existing[0]
            else:
                # Profile doesn't exist, insert it
                cursor.execute("""
                    INSERT INTO profiles (platform, username_or_url, display_name)
                    VALUES (?, ?, ?)
                """, (platform, username_or_url, display_name or username_or_url))
                profile_id = cursor.lastrowid
        
        conn.commit()
        return profile_id
    finally:
        conn.close()


def delete_profile(profile_id: int) -> bool:
    """Delete a profile and all associated posts and comments."""
    conn = get_connection()
    cursor = conn.cursor()
    
    try:
        if USE_POSTGRES:
            # PostgreSQL CASCADE will handle deletions
            cursor.execute("DELETE FROM profiles WHERE id = %s", (profile_id,))
        else:
            # SQLite: delete manually
            cursor.execute("""
                DELETE FROM comments 
                WHERE post_id IN (SELECT id FROM posts WHERE profile_id = ?)
            """, (profile_id,))
            cursor.execute("DELETE FROM posts WHERE profile_id = ?", (profile_id,))
            cursor.execute("DELETE FROM profiles WHERE id = ?", (profile_id,))
        
        conn.commit()
        return cursor.rowcount > 0
    finally:
        conn.close()


def update_profile_apify_token_key(profile_id: int, apify_token_key: Optional[str]) -> None:
    """Actualiza qué API key usa este perfil: facebook_1, facebook_2, instagram, tiktok (o None para auto)."""
    conn = get_connection()
    cursor = conn.cursor()
    try:
        val = (apify_token_key.strip() or None) if apify_token_key else None
        if USE_POSTGRES:
            cursor.execute("UPDATE profiles SET apify_token_key = %s WHERE id = %s", (val, profile_id))
        else:
            cursor.execute("UPDATE profiles SET apify_token_key = ? WHERE id = ?", (val, profile_id))
        conn.commit()
    finally:
        conn.close()


def update_profile_last_analyzed(profile_id: int) -> None:
    """Update the last_analyzed timestamp for a profile."""
    conn = get_connection()
    cursor = conn.cursor()
    
    try:
        if USE_POSTGRES:
            cursor.execute("""
                UPDATE profiles 
                SET last_analyzed = CURRENT_TIMESTAMP 
                WHERE id = %s
            """, (profile_id,))
        else:
            cursor.execute("""
                UPDATE profiles 
                SET last_analyzed = CURRENT_TIMESTAMP 
                WHERE id = ?
            """, (profile_id,))
        
        conn.commit()
    finally:
        conn.close()


def insert_post(
    profile_id: int,
    platform: str,
    post_id: str,
    url: Optional[str] = None,
    text: Optional[str] = None,
    likes: int = 0,
    comments_count: int = 0,
    shares: int = 0,
    views: int = 0,
    posted_at: Optional[datetime] = None
) -> int:
    """
    Insert or update a post. Returns the post database ID.
    No se borran nunca posts anteriores: solo se insertan nuevos o se actualizan existentes
    por (platform, post_id). Los posts ya guardados del perfil se mantienen.
    """
    conn = get_connection()
    cursor = conn.cursor()
    
    try:
        interactions_total = likes + comments_count + shares + (views if views else 0)
        
        if USE_POSTGRES:
            cursor.execute("""
                INSERT INTO posts 
                (profile_id, platform, post_id, url, text, likes, comments_count, 
                 shares, views, interactions_total, posted_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (platform, post_id) DO UPDATE SET
                    profile_id = EXCLUDED.profile_id,
                    url = EXCLUDED.url,
                    text = EXCLUDED.text,
                    likes = EXCLUDED.likes,
                    comments_count = EXCLUDED.comments_count,
                    shares = EXCLUDED.shares,
                    views = EXCLUDED.views,
                    interactions_total = EXCLUDED.interactions_total,
                    posted_at = EXCLUDED.posted_at,
                    scraped_at = CURRENT_TIMESTAMP
                RETURNING id
            """, (
                profile_id, platform, post_id, url, text, likes, comments_count,
                shares, views, interactions_total, posted_at
            ))
            result = cursor.fetchone()
            post_db_id = result[0] if result else None
        else:
            # SQLite: Check if post exists first, then INSERT or UPDATE accordingly
            cursor.execute("SELECT id FROM posts WHERE platform = ? AND post_id = ?", (platform, post_id))
            existing = cursor.fetchone()
            
            if existing:
                # Post exists, update it (prevent duplicate)
                post_db_id = existing[0]
                logger.debug(f"Post already exists (platform={platform}, post_id={post_id[:50]}), updating instead of duplicating")
                cursor.execute("""
                    UPDATE posts SET
                        profile_id = ?,
                        url = ?,
                        text = ?,
                        likes = ?,
                        comments_count = ?,
                        shares = ?,
                        views = ?,
                        interactions_total = ?,
                        posted_at = ?,
                        scraped_at = CURRENT_TIMESTAMP
                    WHERE id = ?
                """, (
                    profile_id, url, text, likes, comments_count,
                    shares, views, interactions_total, posted_at,
                    post_db_id
                ))
            else:
                # Post doesn't exist, insert it
                logger.debug(f"Inserting new post (platform={platform}, post_id={post_id[:50]})")
                cursor.execute("""
                    INSERT INTO posts 
                    (profile_id, platform, post_id, url, text, likes, comments_count, 
                     shares, views, interactions_total, posted_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    profile_id, platform, post_id, url, text, likes, comments_count,
                    shares, views, interactions_total, posted_at
                ))
                post_db_id = cursor.lastrowid
        
        conn.commit()
        return post_db_id
    finally:
        conn.close()


def get_post_profile_and_platform(post_id: int) -> Optional[Tuple[int, str]]:
    """Returns (profile_id, platform) for a post by its internal id, or None."""
    conn = get_connection()
    cursor = conn.cursor()
    try:
        if USE_POSTGRES:
            cursor.execute("SELECT profile_id, platform FROM posts WHERE id = %s", (post_id,))
        else:
            cursor.execute("SELECT profile_id, platform FROM posts WHERE id = ?", (post_id,))
        row = cursor.fetchone()
        if not row:
            return None
        if USE_POSTGRES and hasattr(row, "keys"):
            return (row["profile_id"], (row["platform"] or "").lower())
        return (row[0], (row[1] or "").lower())
    finally:
        conn.close()


def _normalize_comment_text(t: Optional[str]) -> str:
    if not t:
        return ""
    return " ".join(str(t).lower().split())


def comment_exists_same_text_author_for_profile(
    profile_id: int,
    text: Optional[str],
    author: Optional[str]
) -> bool:
    """
    True if the profile already has a comment with the same (normalized text, author).
    Used to avoid storing the same TikTok comment multiple times when the actor
    returns it for several videos.
    """
    norm_text = _normalize_comment_text(text)
    author_clean = (author or "").strip()
    if not norm_text and not author_clean:
        return False
    conn = get_connection()
    cursor = conn.cursor()
    try:
        ph = "%s" if USE_POSTGRES else "?"
        cursor.execute(
            """
            SELECT c.text FROM comments c
            JOIN posts p ON c.post_id = p.id
            WHERE p.profile_id = """ + ph + """ AND TRIM(COALESCE(c.author, '')) = """ + ph,
            (profile_id, author_clean)
        )
        rows = cursor.fetchall()
        for row in rows:
            try:
                existing_text = row["text"]
            except (TypeError, KeyError):
                existing_text = row[0] if row else None
            if _normalize_comment_text(existing_text) == norm_text:
                return True
        return False
    finally:
        conn.close()


def insert_comment(
    post_id: int,
    comment_id: str,
    text: Optional[str] = None,
    author: Optional[str] = None,
    likes: int = 0,
    sentiment_label: Optional[str] = None,
    sentiment_score: Optional[float] = None,
    sentiment_method: Optional[str] = None,
    posted_at: Optional[datetime] = None
) -> None:
    """
    Insert or update a comment.
    Prevents duplicates by checking UNIQUE constraint (post_id, comment_id).
    """
    conn = get_connection()
    cursor = conn.cursor()
    
    try:
        if USE_POSTGRES:
            cursor.execute("""
                INSERT INTO comments 
                (post_id, comment_id, text, author, likes, sentiment_label, 
                 sentiment_score, sentiment_method, posted_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (post_id, comment_id) DO UPDATE SET
                    text = EXCLUDED.text,
                    author = EXCLUDED.author,
                    likes = EXCLUDED.likes,
                    sentiment_label = EXCLUDED.sentiment_label,
                    sentiment_score = EXCLUDED.sentiment_score,
                    sentiment_method = EXCLUDED.sentiment_method,
                    posted_at = EXCLUDED.posted_at,
                    scraped_at = CURRENT_TIMESTAMP
            """, (
                post_id, comment_id, text, author, likes, sentiment_label,
                sentiment_score, sentiment_method, posted_at
            ))
        else:
            # SQLite: Check if comment exists first, then INSERT or UPDATE accordingly
            cursor.execute("SELECT id FROM comments WHERE post_id = ? AND comment_id = ?", (post_id, comment_id))
            existing = cursor.fetchone()
            
            if existing:
                # Comment exists, update it (prevent duplicate)
                logger.debug(f"Comment already exists (post_id={post_id}, comment_id={comment_id[:50]}), updating instead of duplicating")
                cursor.execute("""
                    UPDATE comments SET
                        text = ?,
                        author = ?,
                        likes = ?,
                        sentiment_label = ?,
                        sentiment_score = ?,
                        sentiment_method = ?,
                        posted_at = ?,
                        scraped_at = CURRENT_TIMESTAMP
                    WHERE post_id = ? AND comment_id = ?
                """, (
                    text, author, likes, sentiment_label,
                    sentiment_score, sentiment_method, posted_at,
                    post_id, comment_id
                ))
            else:
                # Comment doesn't exist, insert it
                logger.debug(f"Inserting new comment (post_id={post_id}, comment_id={comment_id[:50]})")
                cursor.execute("""
                    INSERT INTO comments 
                    (post_id, comment_id, text, author, likes, sentiment_label, 
                     sentiment_score, sentiment_method, posted_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    post_id, comment_id, text, author, likes, sentiment_label,
                    sentiment_score, sentiment_method, posted_at
                ))
        
        conn.commit()
    finally:
        conn.close()


def get_posts_for_dashboard(
    platform: Optional[str] = None,
    profile_id: Optional[int] = None,
    min_interactions: int = 0,
    date_from: Optional[datetime] = None,
    date_to: Optional[datetime] = None
) -> List[Dict[str, Any]]:
    """Get posts with filters for dashboard display."""
    conn = get_connection()
    cursor = conn.cursor()
    
    try:
        if USE_POSTGRES:
            cursor = conn.cursor(cursor_factory=RealDictCursor)
            placeholder = "%s"
        else:
            placeholder = "?"
        
        query = """
            SELECT p.*, pr.username_or_url, pr.display_name
            FROM posts p
            JOIN profiles pr ON p.profile_id = pr.id
            WHERE 1=1
        """
        params = []
        
        if platform:
            query += f" AND p.platform = {placeholder}"
            params.append(platform)
        
        if profile_id:
            query += f" AND p.profile_id = {placeholder}"
            params.append(profile_id)
        
        if min_interactions:
            query += f" AND p.interactions_total >= {placeholder}"
            params.append(min_interactions)
        
        if date_from:
            query += f" AND (p.posted_at >= {placeholder} OR p.posted_at IS NULL)"
            params.append(date_from)
        
        if date_to:
            query += f" AND (p.posted_at <= {placeholder} OR p.posted_at IS NULL)"
            params.append(date_to)
        
        query += " ORDER BY p.posted_at DESC"
        
        cursor.execute(query, params)
        
        if USE_POSTGRES:
            rows = cursor.fetchall()
            return [dict(row) for row in rows]
        else:
            rows = cursor.fetchall()
            return [dict(row) for row in rows]
    finally:
        conn.close()


def get_post_by_url(url: str, profile_id: Optional[int] = None) -> Optional[Dict[str, Any]]:
    """Busca un post por su URL (para asociar comentarios importados de Apify)."""
    if not url or not url.strip():
        return None
    conn = get_connection()
    cursor = conn.cursor()
    try:
        if USE_POSTGRES:
            cursor = conn.cursor(cursor_factory=RealDictCursor)
            q = "SELECT id, profile_id, platform, post_id, url FROM posts WHERE url = %s"
            params = [url.strip()]
            if profile_id is not None:
                q += " AND profile_id = %s"
                params.append(profile_id)
            cursor.execute(q, params)
        else:
            q = "SELECT id, profile_id, platform, post_id, url FROM posts WHERE url = ?"
            params = [url.strip()]
            if profile_id is not None:
                q += " AND profile_id = ?"
                params.append(profile_id)
            cursor.execute(q, params)
        row = cursor.fetchone()
        if not row:
            return None
        if USE_POSTGRES:
            return dict(row)
        return dict(zip([c[0] for c in cursor.description], row))
    finally:
        conn.close()


def get_comments_for_dashboard(
    post_id: Optional[int] = None,
    sentiment_label: Optional[str] = None,
    min_likes: int = 0,
    platform: Optional[str] = None,
    profile_id: Optional[int] = None,
    sentiment: Optional[str] = None
) -> List[Dict[str, Any]]:
    """Get comments with filters for dashboard display."""
    conn = get_connection()
    cursor = conn.cursor()
    
    try:
        if USE_POSTGRES:
            cursor = conn.cursor(cursor_factory=RealDictCursor)
            placeholder = "%s"
        else:
            placeholder = "?"
        
        query = """
            SELECT c.*, p.platform, p.post_id as post_external_id, p.profile_id
            FROM comments c
            JOIN posts p ON c.post_id = p.id
            WHERE 1=1
        """
        params = []
        
        if post_id:
            query += f" AND c.post_id = {placeholder}"
            params.append(post_id)
        
        # Support both sentiment_label (old) and sentiment (new) parameters
        if sentiment_label:
            query += f" AND c.sentiment_label = {placeholder}"
            params.append(sentiment_label)
        elif sentiment:
            # Map frontend sentiment to database format
            sentiment_map = {
                'positive': 'POSITIVE',
                'negative': 'NEGATIVE',
                'neutral': 'NEUTRAL'
            }
            db_sentiment = sentiment_map.get(sentiment.lower())
            if db_sentiment:
                query += f" AND c.sentiment_label = {placeholder}"
                params.append(db_sentiment)
        
        if min_likes:
            query += f" AND c.likes >= {placeholder}"
            params.append(min_likes)
        
        if platform:
            query += f" AND p.platform = {placeholder}"
            params.append(platform)
        
        if profile_id:
            query += f" AND p.profile_id = {placeholder}"
            params.append(profile_id)
        
        query += " ORDER BY c.likes DESC, c.posted_at DESC"
        
        cursor.execute(query, params)
        
        if USE_POSTGRES:
            rows = cursor.fetchall()
            return [dict(row) for row in rows]
        else:
            rows = cursor.fetchall()
            return [dict(row) for row in rows]
    finally:
        conn.close()


def get_comments_without_sentiment(
    profile_id: Optional[int] = None,
    platform: Optional[str] = None,
    limit: Optional[int] = None
) -> List[Dict[str, Any]]:
    """Obtiene comentarios que aún no tienen análisis de sentimiento (sentiment_label IS NULL)."""
    conn = get_connection()
    cursor = conn.cursor()
    try:
        if USE_POSTGRES:
            cursor = conn.cursor(cursor_factory=RealDictCursor)
            placeholder = "%s"
        else:
            placeholder = "?"
        query = """
            SELECT c.id, c.post_id, c.comment_id, c.text, c.author, c.likes, c.posted_at
            FROM comments c
            JOIN posts p ON c.post_id = p.id
            WHERE c.sentiment_label IS NULL AND (c.text IS NOT NULL AND TRIM(c.text) != '')
        """
        params = []
        if profile_id:
            query += f" AND p.profile_id = {placeholder}"
            params.append(profile_id)
        if platform:
            query += f" AND p.platform = {placeholder}"
            params.append(platform)
        query += " ORDER BY c.id"
        if limit:
            query += f" LIMIT {placeholder}"
            params.append(limit)
        cursor.execute(query, params)
        rows = cursor.fetchall()
        if USE_POSTGRES:
            return [dict(r) for r in rows]
        return [dict(zip([col[0] for col in cursor.description], row)) for row in rows]
    finally:
        conn.close()


def update_comment_sentiment(
    comment_id_internal: int,
    sentiment_label: str,
    sentiment_score: float,
    sentiment_method: str
) -> None:
    """Actualiza el sentimiento de un comentario por su id interno."""
    conn = get_connection()
    cursor = conn.cursor()
    try:
        if USE_POSTGRES:
            cursor.execute("""
                UPDATE comments SET sentiment_label = %s, sentiment_score = %s, sentiment_method = %s
                WHERE id = %s
            """, (sentiment_label, sentiment_score, sentiment_method, comment_id_internal))
        else:
            cursor.execute("""
                UPDATE comments SET sentiment_label = ?, sentiment_score = ?, sentiment_method = ?
                WHERE id = ?
            """, (sentiment_label, sentiment_score, sentiment_method, comment_id_internal))
        conn.commit()
    finally:
        conn.close()


def get_sentiment_stats(profile_id: Optional[int] = None, platform: Optional[str] = None) -> Dict[str, Any]:
    """Get sentiment statistics for comments."""
    conn = get_connection()
    cursor = conn.cursor()
    
    try:
        if USE_POSTGRES:
            placeholder = "%s"
        else:
            placeholder = "?"
        
        query = """
            SELECT 
                c.sentiment_label,
                COUNT(*) as count,
                AVG(c.sentiment_score) as avg_score
            FROM comments c
            JOIN posts p ON c.post_id = p.id
            WHERE c.sentiment_label IS NOT NULL
        """
        params = []
        
        if profile_id:
            query += f" AND p.profile_id = {placeholder}"
            params.append(profile_id)
        
        if platform:
            query += f" AND p.platform = {placeholder}"
            params.append(platform)
        
        query += " GROUP BY c.sentiment_label"
        
        cursor.execute(query, params)
        rows = cursor.fetchall()
        
        stats = {"POSITIVE": 0, "NEGATIVE": 0, "NEUTRAL": 0}
        total = 0
        
        for row in rows:
            label = row[0]
            count = row[1]
            stats[label] = count
            total += count
        
        # Calculate percentages
        percentages = {}
        for label, count in stats.items():
            percentages[label] = (count / total * 100) if total > 0 else 0
        
        return {
            "counts": stats,
            "percentages": percentages,
            "total": total
        }
    finally:
        conn.close()


def get_most_repeated_comments(
    profile_id: Optional[int] = None,
    platform: Optional[str] = None,
    limit: int = 10
) -> List[Dict[str, Any]]:
    """Get the most repeated comments (by text similarity)."""
    conn = get_connection()
    cursor = conn.cursor()
    
    try:
        if USE_POSTGRES:
            placeholder = "%s"
        else:
            placeholder = "?"
        
        # Get all comments with filters
        query = """
            SELECT 
                c.text,
                c.sentiment_label,
                c.likes,
                c.posted_at,
                p.platform,
                COALESCE(pr.display_name, pr.username_or_url) as profile_name
            FROM comments c
            JOIN posts p ON c.post_id = p.id
            JOIN profiles pr ON p.profile_id = pr.id
            WHERE c.text IS NOT NULL AND LENGTH(TRIM(c.text)) > 0
        """
        params = []
        
        if profile_id:
            query += f" AND p.profile_id = {placeholder}"
            params.append(profile_id)
        
        if platform:
            query += f" AND p.platform = {placeholder}"
            params.append(platform)
        
        query += " ORDER BY c.posted_at DESC"
        
        if USE_POSTGRES:
            cursor.close()
            dict_cursor = conn.cursor(cursor_factory=RealDictCursor)
            dict_cursor.execute(query, params)
            rows = dict_cursor.fetchall()
            dict_cursor.close()
        else:
            cursor.execute(query, params)
            rows = cursor.fetchall()
        
        # Group similar comments (normalize text for comparison)
        from collections import Counter
        import re
        
        # Normalize comments: lowercase, remove extra spaces, remove punctuation for grouping
        comment_groups = {}
        
        for row in rows:
            if USE_POSTGRES:
                text = row['text']
                sentiment = row['sentiment_label']
                likes = row['likes']
                posted_at = row['posted_at']
                platform_name = row['platform']
                profile_name = row['profile_name']
            else:
                # SQLite returns dict-like Row objects when row_factory is set
                text = row['text'] if hasattr(row, 'keys') else row[0]
                sentiment = row['sentiment_label'] if hasattr(row, 'keys') else row[1]
                likes = row['likes'] if hasattr(row, 'keys') else row[2]
                posted_at = row['posted_at'] if hasattr(row, 'keys') else row[3]
                platform_name = row['platform'] if hasattr(row, 'keys') else row[4]
                profile_name = row['profile_name'] if hasattr(row, 'keys') else row[5]
            
            # Normalize for grouping (remove extra spaces, lowercase)
            normalized = re.sub(r'\s+', ' ', text.lower().strip())
            
            if normalized not in comment_groups:
                comment_groups[normalized] = {
                    'text': text,  # Keep original text
                    'count': 0,
                    'total_likes': 0,
                    'sentiments': Counter(),
                    'platforms': Counter(),
                    'first_seen': posted_at,
                    'last_seen': posted_at,
                    'profile_name': profile_name
                }
            
            comment_groups[normalized]['count'] += 1
            comment_groups[normalized]['total_likes'] += likes or 0
            if sentiment:
                comment_groups[normalized]['sentiments'][sentiment] += 1
            comment_groups[normalized]['platforms'][platform_name] += 1
            
            if posted_at and (not comment_groups[normalized]['first_seen'] or posted_at < comment_groups[normalized]['first_seen']):
                comment_groups[normalized]['first_seen'] = posted_at
            if posted_at and (not comment_groups[normalized]['last_seen'] or posted_at > comment_groups[normalized]['last_seen']):
                comment_groups[normalized]['last_seen'] = posted_at
        
        # Convert to list and sort by count
        result = []
        for normalized, data in comment_groups.items():
            if data['count'] > 1:  # Only include repeated comments
                result.append({
                    'text': data['text'],
                    'count': data['count'],
                    'total_likes': data['total_likes'],
                    'avg_likes': data['total_likes'] / data['count'] if data['count'] > 0 else 0,
                    'most_common_sentiment': data['sentiments'].most_common(1)[0][0] if data['sentiments'] else None,
                    'platforms': dict(data['platforms']),
                    'first_seen': data['first_seen'],
                    'last_seen': data['last_seen'],
                    'profile_name': data['profile_name']
                })
        
        # Sort by count (most repeated first)
        result.sort(key=lambda x: x['count'], reverse=True)
        
        return result[:limit]
    finally:
        conn.close()


def export_comments_to_csv(
    profile_id: Optional[int] = None,
    platform: Optional[str] = None,
    sentiment_label: Optional[str] = None,
    date_from: Optional[datetime] = None,
    date_to: Optional[datetime] = None
) -> str:
    """Export comments to CSV format."""
    comments = get_comments_for_dashboard(
        profile_id=profile_id,
        platform=platform,
        sentiment_label=sentiment_label
    )
    
    # Filter by date if provided
    if date_from or date_to:
        filtered_comments = []
        for comment in comments:
            posted_at = comment.get('posted_at')
            if posted_at:
                if isinstance(posted_at, str):
                    posted_at = datetime.fromisoformat(posted_at.replace('Z', '+00:00'))
                if date_from and posted_at < date_from:
                    continue
                if date_to and posted_at > date_to:
                    continue
            filtered_comments.append(comment)
        comments = filtered_comments
    
    # Create CSV
    output = io.StringIO()
    writer = csv.writer(output)
    
    # Write header
    writer.writerow([
        'ID', 'Perfil', 'Plataforma', 'Post ID', 'Texto del Comentario',
        'Autor', 'Likes', 'Sentimiento', 'Puntuación Sentimiento',
        'Fecha Publicación', 'Fecha Scrapeo'
    ])
    
    # Write data
    for comment in comments:
        writer.writerow([
            comment.get('id', ''),
            comment.get('profile_name', '') or comment.get('username_or_url', ''),
            comment.get('platform', ''),
            comment.get('post_external_id', ''),
            comment.get('text', ''),
            comment.get('author', ''),
            comment.get('likes', 0),
            comment.get('sentiment_label', ''),
            comment.get('sentiment_score', ''),
            comment.get('posted_at', ''),
            comment.get('scraped_at', '')
        ])
    
    return output.getvalue()


def export_posts_to_csv(
    profile_id: Optional[int] = None,
    platform: Optional[str] = None,
    date_from: Optional[datetime] = None,
    date_to: Optional[datetime] = None
) -> str:
    """Export posts to CSV format."""
    posts = get_posts_for_dashboard(
        profile_id=profile_id,
        platform=platform,
        date_from=date_from,
        date_to=date_to
    )
    
    # Create CSV
    output = io.StringIO()
    writer = csv.writer(output)
    
    # Write header
    writer.writerow([
        'ID', 'Perfil', 'Plataforma', 'Post ID', 'URL', 'Texto',
        'Likes', 'Comentarios', 'Compartidos', 'Vistas', 'Interacciones Totales',
        'Fecha Publicación', 'Fecha Scrapeo'
    ])
    
    # Write data
    for post in posts:
        writer.writerow([
            post.get('id', ''),
            post.get('display_name', '') or post.get('username_or_url', ''),
            post.get('platform', ''),
            post.get('post_id', ''),
            post.get('url', ''),
            post.get('text', ''),
            post.get('likes', 0),
            post.get('comments_count', 0),
            post.get('shares', 0),
            post.get('views', 0),
            post.get('interactions_total', 0),
            post.get('posted_at', ''),
            post.get('scraped_at', '')
        ])
    
    return output.getvalue()


def export_interactions_to_csv(
    profile_id: Optional[int] = None,
    platform: Optional[str] = None,
    date_from: Optional[datetime] = None,
    date_to: Optional[datetime] = None
) -> str:
    """Export interaction statistics to CSV format (aggregated by day)."""
    posts = get_posts_for_dashboard(
        profile_id=profile_id,
        platform=platform,
        date_from=date_from,
        date_to=date_to
    )
    
    # Aggregate by date
    from collections import defaultdict
    daily_stats = defaultdict(lambda: {
        'date': '',
        'posts': 0,
        'likes': 0,
        'comments': 0,
        'shares': 0,
        'views': 0,
        'interactions_total': 0,
        'platform': platform or 'Todas'
    })
    
    for post in posts:
        posted_at = post.get('posted_at')
        if posted_at:
            if isinstance(posted_at, str):
                posted_at = datetime.fromisoformat(posted_at.replace('Z', '+00:00'))
            date_key = posted_at.date().isoformat()
            
            daily_stats[date_key]['date'] = date_key
            daily_stats[date_key]['posts'] += 1
            daily_stats[date_key]['likes'] += post.get('likes', 0) or 0
            daily_stats[date_key]['comments'] += post.get('comments_count', 0) or 0
            daily_stats[date_key]['shares'] += post.get('shares', 0) or 0
            daily_stats[date_key]['views'] += post.get('views', 0) or 0
            daily_stats[date_key]['interactions_total'] += post.get('interactions_total', 0) or 0
            if not daily_stats[date_key]['platform']:
                daily_stats[date_key]['platform'] = post.get('platform', '')
    
    # Create CSV
    output = io.StringIO()
    writer = csv.writer(output)
    
    # Write header
    writer.writerow([
        'Fecha', 'Plataforma', 'Posts', 'Likes', 'Comentarios',
        'Compartidos', 'Vistas', 'Interacciones Totales'
    ])
    
    # Write data (sorted by date)
    sorted_dates = sorted(daily_stats.keys())
    for date_key in sorted_dates:
        stats = daily_stats[date_key]
        writer.writerow([
            stats['date'],
            stats['platform'],
            stats['posts'],
            stats['likes'],
            stats['comments'],
            stats['shares'],
            stats['views'],
            stats['interactions_total']
        ])
    
    return output.getvalue()
