"""
Utility functions for URL normalization, calculations, and common operations.
"""
import re
from typing import Optional, Tuple
from urllib.parse import urlparse, parse_qs


def normalize_username_or_url(input_str: str) -> Tuple[str, Optional[str]]:
    """
    Normalize username or URL input.
    Returns (normalized_username, platform) tuple.
    Platform can be 'instagram', 'tiktok', 'facebook', or None if unclear.
    """
    input_str = input_str.strip()
    
    # Remove @ symbol if present
    if input_str.startswith("@"):
        input_str = input_str[1:]
    
    # Check if it's a URL
    if input_str.startswith(("http://", "https://")):
        try:
            parsed = urlparse(input_str)
            domain = parsed.netloc.lower()
            
            # Extract username from URL
            path_parts = [p for p in parsed.path.split("/") if p]
            
            if "instagram.com" in domain:
                if path_parts:
                    username = path_parts[0]
                    return username, "instagram"
            elif "tiktok.com" in domain:
                if path_parts and path_parts[0] == "@":
                    username = path_parts[1] if len(path_parts) > 1 else None
                elif path_parts:
                    username = path_parts[0].lstrip("@")
                else:
                    username = None
                if username:
                    return username, "tiktok"
            elif "facebook.com" in domain:
                if path_parts:
                    username = path_parts[0]
                    return username, "facebook"
        except Exception:
            pass
    
    # If it's just a username, try to detect platform from common patterns
    # For now, return as-is and let the user select platform
    return input_str, None


def calculate_interactions_total(likes: int = 0, comments: int = 0, shares: int = 0, views: int = 0) -> int:
    """Calculate total interactions from individual metrics."""
    return likes + comments + shares + (views if views else 0)


def format_number(num: int) -> str:
    """Format large numbers with K, M suffixes."""
    if num >= 1_000_000:
        return f"{num / 1_000_000:.1f}M"
    elif num >= 1_000:
        return f"{num / 1_000:.1f}K"
    return str(num)


def parse_datetime_str(dt_str: Optional[str]) -> Optional[str]:
    """Parse and normalize datetime string."""
    if not dt_str:
        return None
    # Return as-is for now, can be enhanced with proper parsing
    return dt_str


def validate_apify_token(token: str) -> bool:
    """Basic validation of Apify token format."""
    if not token or len(token) < 10:
        return False
    # Apify tokens typically start with 'apify_api_' or are UUIDs
    return True


def clean_text(text: Optional[str]) -> Optional[str]:
    """Clean and normalize text content."""
    if not text:
        return None
    # Remove extra whitespace
    text = re.sub(r'\s+', ' ', text.strip())
    return text if text else None
