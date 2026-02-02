"""
Configuration management module.
Handles loading and saving all application settings from/to SQLite database.
"""
from typing import Any, Dict, List, Optional
from db_utils import get_config, set_config, init_database

# Default configuration values
DEFAULT_CONFIG = {
    "apify_token": "",
    "huggingface_model": "cardiffnlp/twitter-xlm-roberta-base-sentiment",
    "keywords_positive": ["excelente", "recomiendo", "genial", "perfecto", "amazing", "great", "love", "best"],
    "keywords_negative": ["malo", "horrible", "terrible", "pésimo", "bad", "worst", "hate", "disappointed"],
    "actor_instagram_posts": "shu8hvrXbJbY3Eb9W",
    "actor_instagram_comments": "instagram-comment-scraper",
    "actor_tiktok_posts": "GdWCkxBtKWOsKjdch",  # clockworks/tiktok-scraper (the correct actor)
    "actor_tiktok_comments": "tiktok-comments-scraper",
    "actor_facebook_posts": "apify/facebook-posts-scraper",  # Official Apify actor
    "actor_facebook_comments": "us5srxAYnsrkgUv2v",  # apify/facebook-comments-scraper - Official Facebook comments actor
    "default_limit_posts": 50,
    "default_limit_comments": 200,
    "auto_skip_recent": True,  # Skip profiles analyzed in last 7 days
    "tiktok_date_from": None,  # Filter TikTok posts from this date (YYYY-MM-DD format, None = no filter)
    "tiktok_date_to": None,  # Filter TikTok posts to this date (YYYY-MM-DD format, None = no filter)
    "tiktok_last_days": 7,  # Alternative: filter by last N days (0 = no filter)
}


def ensure_database_initialized() -> None:
    """Ensure database is initialized with default config if needed."""
    init_database()
    
    # Set default values if they don't exist
    for key, value in DEFAULT_CONFIG.items():
        if get_config(key) is None:
            set_config(key, value)


def get_apify_token() -> str:
    """Get Apify API token from configuration."""
    return get_config("apify_token", "")


def set_apify_token(token: str) -> None:
    """Set Apify API token in configuration."""
    set_config("apify_token", token)


def get_huggingface_model() -> str:
    """Get HuggingFace model name from configuration."""
    return get_config("huggingface_model", DEFAULT_CONFIG["huggingface_model"])


def set_huggingface_model(model: str) -> None:
    """Set HuggingFace model name in configuration."""
    set_config("huggingface_model", model)


def get_keywords_positive() -> List[str]:
    """Get list of positive keywords from configuration."""
    keywords = get_config("keywords_positive", DEFAULT_CONFIG["keywords_positive"])
    if isinstance(keywords, list):
        return keywords
    return DEFAULT_CONFIG["keywords_positive"]


def set_keywords_positive(keywords: List[str]) -> None:
    """Set list of positive keywords in configuration."""
    set_config("keywords_positive", keywords)


def get_keywords_negative() -> List[str]:
    """Get list of negative keywords from configuration."""
    keywords = get_config("keywords_negative", DEFAULT_CONFIG["keywords_negative"])
    if isinstance(keywords, list):
        return keywords
    return DEFAULT_CONFIG["keywords_negative"]


def set_keywords_negative(keywords: List[str]) -> None:
    """Set list of negative keywords in configuration."""
    set_config("keywords_negative", keywords)


def get_actor_id(platform: str, actor_type: str = "posts") -> str:
    """Get Apify Actor ID for a platform and type (posts or comments)."""
    key = f"actor_{platform.lower()}_{actor_type}"
    return get_config(key, DEFAULT_CONFIG.get(key, ""))


def set_actor_id(platform: str, actor_type: str, actor_id: str) -> None:
    """Set Apify Actor ID for a platform and type."""
    key = f"actor_{platform.lower()}_{actor_type}"
    set_config(key, actor_id)


def get_default_limit_posts() -> int:
    """Get default limit for number of posts to scrape."""
    return get_config("default_limit_posts", DEFAULT_CONFIG["default_limit_posts"])


def set_default_limit_posts(limit: int) -> None:
    """Set default limit for number of posts to scrape."""
    set_config("default_limit_posts", limit)


def get_default_limit_comments() -> int:
    """Get default limit for number of comments per post."""
    return get_config("default_limit_comments", DEFAULT_CONFIG["default_limit_comments"])


def set_default_limit_comments(limit: int) -> None:
    """Set default limit for number of comments per post."""
    set_config("default_limit_comments", limit)


def get_auto_skip_recent() -> bool:
    """Get whether to auto-skip recently analyzed profiles."""
    return get_config("auto_skip_recent", DEFAULT_CONFIG["auto_skip_recent"])


def set_auto_skip_recent(enabled: bool) -> None:
    """Set whether to auto-skip recently analyzed profiles."""
    set_config("auto_skip_recent", enabled)


def get_tiktok_date_from() -> Optional[str]:
    """Get TikTok filter date from (YYYY-MM-DD format)."""
    return get_config("tiktok_date_from", DEFAULT_CONFIG["tiktok_date_from"])


def set_tiktok_date_from(date_str: Optional[str]) -> None:
    """Set TikTok filter date from (YYYY-MM-DD format or None)."""
    set_config("tiktok_date_from", date_str)


def get_tiktok_date_to() -> Optional[str]:
    """Get TikTok filter date to (YYYY-MM-DD format)."""
    return get_config("tiktok_date_to", DEFAULT_CONFIG["tiktok_date_to"])


def set_tiktok_date_to(date_str: Optional[str]) -> None:
    """Set TikTok filter date to (YYYY-MM-DD format or None)."""
    set_config("tiktok_date_to", date_str)


def get_tiktok_last_days() -> int:
    """Get TikTok filter by last N days (0 = no filter)."""
    value = get_config("tiktok_last_days", DEFAULT_CONFIG["tiktok_last_days"])
    # Ensure it's an integer (config might store as string)
    try:
        return int(value) if value is not None else DEFAULT_CONFIG["tiktok_last_days"]
    except (ValueError, TypeError):
        return DEFAULT_CONFIG["tiktok_last_days"]


def set_tiktok_last_days(days: int) -> None:
    """Set TikTok filter by last N days (0 = no filter)."""
    set_config("tiktok_last_days", days)


def get_all_config() -> Dict[str, Any]:
    """Get all configuration as a dictionary."""
    return {
        "apify_token": get_apify_token(),
        "huggingface_model": get_huggingface_model(),
        "keywords_positive": get_keywords_positive(),
        "keywords_negative": get_keywords_negative(),
        "actor_instagram_posts": get_actor_id("instagram", "posts"),
        "actor_instagram_comments": get_actor_id("instagram", "comments"),
        "actor_tiktok_posts": get_actor_id("tiktok", "posts"),
        "actor_tiktok_comments": get_actor_id("tiktok", "comments"),
        "actor_facebook_posts": get_actor_id("facebook", "posts"),
        "actor_facebook_comments": get_actor_id("facebook", "comments"),
        "default_limit_posts": get_default_limit_posts(),
        "default_limit_comments": get_default_limit_comments(),
        "auto_skip_recent": get_auto_skip_recent(),
        "tiktok_date_from": get_tiktok_date_from(),
        "tiktok_date_to": get_tiktok_date_to(),
        "tiktok_last_days": get_tiktok_last_days(),
    }
