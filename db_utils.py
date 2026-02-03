"""
Database utilities for SQLite and PostgreSQL operations.
Handles initialization, schema creation, and common database operations.
Automatically uses PostgreSQL if DATABASE_URL is set (production), otherwise uses SQLite (development).
"""
import json
import os
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

# Database configuration
DB_PATH = Path("social_media_analytics.db")
DATABASE_URL = os.getenv("DATABASE_URL")

# Determine which database to use
USE_POSTGRES = PSYCOPG2_AVAILABLE and DATABASE_URL is not None
USE_SQLITE = not USE_POSTGRES and SQLITE_AVAILABLE

if not USE_POSTGRES and not USE_SQLITE:
    raise RuntimeError("Neither PostgreSQL nor SQLite is available. Please install psycopg2-binary or ensure SQLite is available.")


def get_connection():
    """Get a database connection (PostgreSQL or SQLite)."""
    if USE_POSTGRES:
        # Parse DATABASE_URL (format: postgresql://user:password@host:port/database)
        # Render provides DATABASE_URL in this format
        conn = psycopg2.connect(DATABASE_URL)
        return conn
    else:
        # SQLite fallback
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
        SELECT id, platform, username_or_url, display_name, last_analyzed, created_at
        FROM profiles
        ORDER BY platform, username_or_url
    """
    return _execute_query(query)


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
            try:
                cursor.execute("""
                    INSERT INTO profiles (platform, username_or_url, display_name)
                    VALUES (?, ?, ?)
                """, (platform, username_or_url, display_name or username_or_url))
                profile_id = cursor.lastrowid
            except sqlite3.IntegrityError:
                # Profile already exists
                conn.rollback()
                cursor.execute("""
                    SELECT id FROM profiles 
                    WHERE platform = ? AND username_or_url = ?
                """, (platform, username_or_url))
                row = cursor.fetchone()
                profile_id = row[0] if row else None
        
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
    """Insert or update a post. Returns the post database ID."""
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
            cursor.execute("""
                INSERT OR REPLACE INTO posts 
                (profile_id, platform, post_id, url, text, likes, comments_count, 
                 shares, views, interactions_total, posted_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                profile_id, platform, post_id, url, text, likes, comments_count,
                shares, views, interactions_total, posted_at
            ))
            # Get the post ID
            cursor.execute("SELECT id FROM posts WHERE platform = ? AND post_id = ?", (platform, post_id))
            row = cursor.fetchone()
            post_db_id = row[0] if row else cursor.lastrowid
        
        conn.commit()
        return post_db_id
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
    """Insert or update a comment."""
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
            cursor.execute("""
                INSERT OR REPLACE INTO comments 
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
