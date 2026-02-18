"""
Configuration management module.
Handles loading and saving all application settings from/to SQLite database.
"""
from typing import Any, Dict, List, Optional
from db_utils import get_config, set_config, init_database

# Default configuration values
# API keys por plataforma/perfil: una para cada perfil Facebook, una Instagram, una TikTok
DEFAULT_CONFIG = {
    "apify_token": "",  # Token por defecto (fallback)
    "apify_token_facebook_1": "",
    "apify_token_facebook_2": "",
    "apify_token_instagram": "",
    "apify_token_tiktok": "",
    "huggingface_model": "cardiffnlp/twitter-xlm-roberta-base-sentiment",
    # Afinadas para comentarios de redes (Riobamba/EC): positivas y negativas
    "keywords_positive": [
        "excelente", "exelente", "recomiendo", "genial", "perfecto", "amazing", "great", "love", "best",
        "chevere", "chévere", "maravilla", "disfrute", "hermosura", "bienvenido", "dale", "desarrollo",
        "despertando", "gusto", "balneario", "visitar", "carnaval",
    ],
    "keywords_negative": [
        "malo", "horrible", "terrible", "pésimo", "bad", "worst", "hate", "disappointed",
        "mierda", "asco", "huecos", "polvo", "delincuencia", "reelección", "pagaron", "puro polvo",
        "no hace nada", "no hace", "tierra", "inconcluso", "abandonado", "bache", "dejaron",
    ],
    "actor_instagram_posts": "shu8hvrXbJbY3Eb9W",
    "actor_instagram_comments": "instagram-comment-scraper",
    "actor_tiktok_posts": "GdWCkxBtKWOsKjdch",  # clockworks/tiktok-scraper (the correct actor)
    "actor_tiktok_comments": "tiktok-comments-scraper",
    "actor_facebook_posts": "apify/facebook-posts-scraper",  # Official Apify actor
    "actor_facebook_comments": "us5srxAYnsrkgUv2v",  # apify/facebook-comments-scraper - Official Facebook comments actor
    "default_limit_posts": 50,
    "default_limit_comments": 200,
    "auto_skip_recent": True,  # Skip profiles analyzed in last 7 days
    "date_from": None,  # Filter posts from this date for ALL platforms (YYYY-MM-DD format, None = no filter)
    "date_to": None,  # Filter posts to this date for ALL platforms (YYYY-MM-DD format, None = no filter)
    "last_days": 7,  # Alternative: filter by last N days for ALL platforms (0 = no filter)
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


# Tokens por plataforma/perfil (repartir cuota: Facebook x2, Instagram, TikTok)
def _get_apify_token_key(key: str) -> str:
    return get_config(key, "")


def _set_apify_token_key(key: str, token: str) -> None:
    set_config(key, token)


def get_apify_token_facebook_1() -> str:
    return _get_apify_token_key("apify_token_facebook_1")


def set_apify_token_facebook_1(token: str) -> None:
    _set_apify_token_key("apify_token_facebook_1", token)


def get_apify_token_facebook_2() -> str:
    return _get_apify_token_key("apify_token_facebook_2")


def set_apify_token_facebook_2(token: str) -> None:
    _set_apify_token_key("apify_token_facebook_2", token)


def get_apify_token_instagram() -> str:
    return _get_apify_token_key("apify_token_instagram")


def set_apify_token_instagram(token: str) -> None:
    _set_apify_token_key("apify_token_instagram", token)


def get_apify_token_tiktok() -> str:
    return _get_apify_token_key("apify_token_tiktok")


def set_apify_token_tiktok(token: str) -> None:
    _set_apify_token_key("apify_token_tiktok", token)


def has_any_apify_token() -> bool:
    """True si hay al menos un token configurado (por defecto o por plataforma)."""
    return bool(
        (get_apify_token() or "").strip()
        or (get_apify_token_facebook_1() or "").strip()
        or (get_apify_token_facebook_2() or "").strip()
        or (get_apify_token_instagram() or "").strip()
        or (get_apify_token_tiktok() or "").strip()
    )


def get_apify_token_for_profile(profile_id: Optional[int] = None, profile: Optional[Dict[str, Any]] = None) -> str:
    """
    Devuelve el token de Apify a usar para un perfil.
    - Si el perfil tiene apify_token_key (facebook_1, facebook_2, instagram, tiktok), usa ese token.
    - Si no: Instagram → token Instagram; TikTok → token TikTok; Facebook → por orden de perfil:
      primer perfil Facebook (por id) usa facebook_1, el segundo facebook_2, etc.
    """
    from db_utils import get_profile_by_id, get_all_profiles
    p = profile or (get_profile_by_id(profile_id) if profile_id else None)
    if not p:
        return get_apify_token()
    pid = p.get("id") or profile_id
    key = (p.get("apify_token_key") or "").strip()
    if key:
        token = get_config(f"apify_token_{key}", "")
        if token:
            return token
    platform = (p.get("platform") or "").lower()
    if platform == "facebook":
        t1, t2 = get_apify_token_facebook_1(), get_apify_token_facebook_2()
        # Sin key asignada: primer perfil Facebook = facebook_1, segundo = facebook_2
        all_profiles = get_all_profiles()
        facebook_ids = sorted([pr["id"] for pr in all_profiles if (pr.get("platform") or "").lower() == "facebook"])
        try:
            idx = facebook_ids.index(pid)
            if idx == 0 and t1:
                return t1
            if idx == 1 and t2:
                return t2
        except (ValueError, TypeError):
            pass
        return t1 or t2 or get_apify_token()
    if platform == "instagram":
        return get_apify_token_instagram() or get_apify_token()
    if platform == "tiktok":
        return get_apify_token_tiktok() or get_apify_token()
    return get_apify_token()


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
    v = get_config("default_limit_posts", DEFAULT_CONFIG["default_limit_posts"])
    return int(v) if v is not None else DEFAULT_CONFIG["default_limit_posts"]


def set_default_limit_posts(limit: int) -> None:
    """Set default limit for number of posts to scrape."""
    set_config("default_limit_posts", int(limit))


def get_default_limit_comments() -> int:
    """Get default limit for number of comments per post."""
    v = get_config("default_limit_comments", DEFAULT_CONFIG["default_limit_comments"])
    return int(v) if v is not None else DEFAULT_CONFIG["default_limit_comments"]


def set_default_limit_comments(limit: int) -> None:
    """Set default limit for number of comments per post."""
    set_config("default_limit_comments", int(limit))


def get_auto_skip_recent() -> bool:
    """Get whether to auto-skip recently analyzed profiles."""
    return get_config("auto_skip_recent", DEFAULT_CONFIG["auto_skip_recent"])


def set_auto_skip_recent(enabled: bool) -> None:
    """Set whether to auto-skip recently analyzed profiles."""
    set_config("auto_skip_recent", enabled)


def get_date_from() -> Optional[str]:
    """Get date filter from for ALL platforms (YYYY-MM-DD format)."""
    return get_config("date_from", DEFAULT_CONFIG["date_from"])


def set_date_from(date_str: Optional[str]) -> None:
    """Set date filter from for ALL platforms (YYYY-MM-DD format or None)."""
    set_config("date_from", date_str)


def get_date_to() -> Optional[str]:
    """Get date filter to for ALL platforms (YYYY-MM-DD format)."""
    return get_config("date_to", DEFAULT_CONFIG["date_to"])


def set_date_to(date_str: Optional[str]) -> None:
    """Set date filter to for ALL platforms (YYYY-MM-DD format or None)."""
    set_config("date_to", date_str)


def get_last_days() -> int:
    """Get last N days filter for ALL platforms (0 = no filter)."""
    value = get_config("last_days", DEFAULT_CONFIG["last_days"])
    # Ensure it's an integer (config might store as string)
    try:
        return int(value) if value is not None else DEFAULT_CONFIG["last_days"]
    except (ValueError, TypeError):
        return DEFAULT_CONFIG["last_days"]


def set_last_days(days: int) -> None:
    """Set last N days filter for ALL platforms (0 = no filter)."""
    set_config("last_days", days)


def get_all_config() -> Dict[str, Any]:
    """Get all configuration as a dictionary."""
    return {
        "apify_token": get_apify_token(),
        "apify_token_facebook_1": get_apify_token_facebook_1(),
        "apify_token_facebook_2": get_apify_token_facebook_2(),
        "apify_token_instagram": get_apify_token_instagram(),
        "apify_token_tiktok": get_apify_token_tiktok(),
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
        "date_from": get_date_from(),
        "date_to": get_date_to(),
        "last_days": get_last_days(),
    }
