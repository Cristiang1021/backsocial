"""
Database utilities for SQLite operations.
Handles initialization, schema creation, and common database operations.
"""
import sqlite3
import json
from typing import Any, Dict, List, Optional, Tuple
from datetime import datetime
from pathlib import Path

DB_PATH = Path("social_media_analytics.db")


def get_connection() -> sqlite3.Connection:
    """Get a database connection."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_database() -> None:
    """Initialize database with all required tables."""
    conn = get_connection()
    cursor = conn.cursor()
    
    # Config table: key-value store for all settings
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS config (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL
        )
    """)
    
    # Profiles table: stores monitored profiles
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
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_posts_profile ON posts(profile_id)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_posts_platform ON posts(platform)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_comments_post ON comments(post_id)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_comments_sentiment ON comments(sentiment_label)")
    
    conn.commit()
    conn.close()


def get_config(key: str, default: Any = None) -> Any:
    """Get a configuration value from the database."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT value FROM config WHERE key = ?", (key,))
    row = cursor.fetchone()
    conn.close()
    
    if row:
        try:
            return json.loads(row[0])
        except json.JSONDecodeError:
            return row[0]
    return default


def set_config(key: str, value: Any) -> None:
    """Set a configuration value in the database."""
    conn = get_connection()
    cursor = conn.cursor()
    
    if isinstance(value, (dict, list)):
        value = json.dumps(value)
    else:
        value = str(value)
    
    cursor.execute(
        "INSERT OR REPLACE INTO config (key, value) VALUES (?, ?)",
        (key, value)
    )
    conn.commit()
    conn.close()


def get_all_profiles() -> List[Dict[str, Any]]:
    """Get all profiles from the database."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT id, platform, username_or_url, display_name, last_analyzed, created_at
        FROM profiles
        ORDER BY platform, username_or_url
    """)
    rows = cursor.fetchall()
    conn.close()
    
    return [dict(row) for row in rows]


def add_profile(platform: str, username_or_url: str, display_name: Optional[str] = None) -> Optional[int]:
    """Add a new profile to the database. Returns the profile ID."""
    conn = get_connection()
    cursor = conn.cursor()
    
    try:
        cursor.execute("""
            INSERT INTO profiles (platform, username_or_url, display_name)
            VALUES (?, ?, ?)
        """, (platform, username_or_url, display_name or username_or_url))
        profile_id = cursor.lastrowid
        conn.commit()
        return profile_id
    except sqlite3.IntegrityError:
        # Profile already exists
        conn.rollback()
        cursor.execute("""
            SELECT id FROM profiles 
            WHERE platform = ? AND username_or_url = ?
        """, (platform, username_or_url))
        row = cursor.fetchone()
        return row[0] if row else None
    finally:
        conn.close()


def delete_profile(profile_id: int) -> bool:
    """Delete a profile and all associated posts and comments."""
    conn = get_connection()
    cursor = conn.cursor()
    
    try:
        # Delete comments first (foreign key constraint)
        cursor.execute("""
            DELETE FROM comments 
            WHERE post_id IN (SELECT id FROM posts WHERE profile_id = ?)
        """, (profile_id,))
        
        # Delete posts
        cursor.execute("DELETE FROM posts WHERE profile_id = ?", (profile_id,))
        
        # Delete profile
        cursor.execute("DELETE FROM profiles WHERE id = ?", (profile_id,))
        
        conn.commit()
        return cursor.rowcount > 0
    finally:
        conn.close()


def update_profile_last_analyzed(profile_id: int) -> None:
    """Update the last_analyzed timestamp for a profile."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        UPDATE profiles 
        SET last_analyzed = CURRENT_TIMESTAMP 
        WHERE id = ?
    """, (profile_id,))
    conn.commit()
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
    
    interactions_total = likes + comments_count + shares + (views if views else 0)
    
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
    conn.close()
    
    return post_db_id


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
    
    query = """
        SELECT p.*, pr.username_or_url, pr.display_name
        FROM posts p
        JOIN profiles pr ON p.profile_id = pr.id
        WHERE 1=1
    """
    params = []
    
    if platform:
        query += " AND p.platform = ?"
        params.append(platform)
    
    if profile_id:
        query += " AND p.profile_id = ?"
        params.append(profile_id)
    
    if min_interactions:
        query += " AND p.interactions_total >= ?"
        params.append(min_interactions)
    
    if date_from:
        query += " AND (p.posted_at >= ? OR p.posted_at IS NULL)"
        params.append(date_from)
    
    if date_to:
        query += " AND (p.posted_at <= ? OR p.posted_at IS NULL)"
        params.append(date_to)
    
    query += " ORDER BY p.posted_at DESC"
    
    cursor.execute(query, params)
    rows = cursor.fetchall()
    conn.close()
    
    return [dict(row) for row in rows]


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
    
    query = """
        SELECT c.*, p.platform, p.post_id as post_external_id, p.profile_id
        FROM comments c
        JOIN posts p ON c.post_id = p.id
        WHERE 1=1
    """
    params = []
    
    if post_id:
        query += " AND c.post_id = ?"
        params.append(post_id)
    
    # Support both sentiment_label (old) and sentiment (new) parameters
    if sentiment_label:
        query += " AND c.sentiment_label = ?"
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
            query += " AND c.sentiment_label = ?"
            params.append(db_sentiment)
    
    if min_likes:
        query += " AND c.likes >= ?"
        params.append(min_likes)
    
    if platform:
        query += " AND p.platform = ?"
        params.append(platform)
    
    if profile_id:
        query += " AND p.profile_id = ?"
        params.append(profile_id)
    
    query += " ORDER BY c.likes DESC, c.posted_at DESC"
    
    cursor.execute(query, params)
    rows = cursor.fetchall()
    conn.close()
    
    return [dict(row) for row in rows]


def get_sentiment_stats(profile_id: Optional[int] = None, platform: Optional[str] = None) -> Dict[str, Any]:
    """Get sentiment statistics for comments."""
    conn = get_connection()
    cursor = conn.cursor()
    
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
        query += " AND p.profile_id = ?"
        params.append(profile_id)
    
    if platform:
        query += " AND p.platform = ?"
        params.append(platform)
    
    query += " GROUP BY c.sentiment_label"
    
    cursor.execute(query, params)
    rows = cursor.fetchall()
    conn.close()
    
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
