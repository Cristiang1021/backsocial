"""
FastAPI REST API for Social Media Analytics Dashboard.
Provides endpoints for profiles, posts, comments, analysis, and configuration.
"""
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta
import logging

# Import existing modules
from config import (
    ensure_database_initialized, get_all_config, set_apify_token, get_apify_token,
    set_huggingface_model, get_huggingface_model, set_keywords_positive, get_keywords_positive,
    set_keywords_negative, get_keywords_negative, set_actor_id, get_actor_id,
    set_default_limit_posts, get_default_limit_posts, set_default_limit_comments,
    get_default_limit_comments, set_auto_skip_recent, get_auto_skip_recent,
    set_date_from, get_date_from, set_date_to, get_date_to,
    set_last_days, get_last_days
)
from db_utils import (
    get_all_profiles, add_profile, delete_profile,
    get_posts_for_dashboard, get_comments_for_dashboard, get_sentiment_stats
)
from scraper import analyze_profiles, ApifyScraper
from analyzer import reload_analyzer

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize database
ensure_database_initialized()

# Create FastAPI app
app = FastAPI(
    title="Social Media Analytics API",
    description="API REST para el dashboard de análisis de redes sociales",
    version="1.0.0"
)

# CORS middleware
# Production frontend URL
PRODUCTION_FRONTEND_URL = "https://frontsocial-777z1xvr4-cristiang1021s-projects.vercel.app"

# Allowed origins: production frontend + localhost for development
allowed_origins = [
    PRODUCTION_FRONTEND_URL,
    "http://localhost:3000",
    "http://127.0.0.1:3000",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Pydantic models for request/response
class ProfileCreate(BaseModel):
    platform: str
    username_or_url: str

class ProfileResponse(BaseModel):
    id: int
    platform: str
    username_or_url: str
    display_name: Optional[str] = None
    last_analyzed: Optional[str] = None
    created_at: Optional[str] = None

class AnalysisRequest(BaseModel):
    profile_ids: Optional[List[int]] = None
    force: bool = False

class ConfigUpdate(BaseModel):
    key: str
    value: Any

class DateFromUpdate(BaseModel):
    date_from: Optional[str] = None

class DateToUpdate(BaseModel):
    date_to: Optional[str] = None

class LastDaysUpdate(BaseModel):
    last_days: int

# ==================== PROFILES ENDPOINTS ====================

@app.get("/api/profiles", response_model=List[ProfileResponse])
def get_profiles():
    """Get all profiles."""
    try:
        profiles = get_all_profiles()
        return profiles
    except Exception as e:
        logger.error(f"Error getting profiles: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/profiles", response_model=ProfileResponse)
def create_profile(profile: ProfileCreate):
    """Create a new profile."""
    try:
        profile_id = add_profile(profile.platform, profile.username_or_url)
        profiles = get_all_profiles()
        new_profile = next((p for p in profiles if p["id"] == profile_id), None)
        if not new_profile:
            raise HTTPException(status_code=404, detail="Profile not found after creation")
        return new_profile
    except Exception as e:
        logger.error(f"Error creating profile: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.delete("/api/profiles/{profile_id}")
def delete_profile_endpoint(profile_id: int):
    """Delete a profile."""
    try:
        success = delete_profile(profile_id)
        if not success:
            raise HTTPException(status_code=404, detail="Profile not found")
        return {"success": True, "message": "Profile deleted successfully"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting profile: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# ==================== POSTS ENDPOINTS ====================

@app.get("/api/posts")
def get_posts(
    platform: Optional[str] = Query(None, description="Filter by platform"),
    profile_id: Optional[int] = Query(None, description="Filter by profile ID"),
    min_interactions: int = Query(0, description="Minimum interactions"),
    date_from: Optional[str] = Query(None, description="Start date (YYYY-MM-DD)"),
    date_to: Optional[str] = Query(None, description="End date (YYYY-MM-DD)"),
    limit: int = Query(100, description="Maximum number of posts"),
    offset: int = Query(0, description="Offset for pagination")
):
    """Get posts with filters."""
    try:
        date_from_obj = None
        date_to_obj = None
        
        if date_from:
            try:
                date_from_obj = datetime.strptime(date_from, "%Y-%m-%d")
            except ValueError:
                raise HTTPException(status_code=400, detail="Invalid date_from format. Use YYYY-MM-DD")
        
        if date_to:
            try:
                date_to_obj = datetime.strptime(date_to, "%Y-%m-%d")
            except ValueError:
                raise HTTPException(status_code=400, detail="Invalid date_to format. Use YYYY-MM-DD")
        
        posts = get_posts_for_dashboard(
            platform=platform,
            profile_id=profile_id,
            min_interactions=min_interactions,
            date_from=date_from_obj,
            date_to=date_to_obj
        )
        
        # Simple pagination
        total = len(posts)
        posts = posts[offset:offset + limit]
        
        return {
            "data": posts,
            "total": total,
            "limit": limit,
            "offset": offset
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting posts: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# ==================== COMMENTS ENDPOINTS ====================

@app.get("/api/comments")
def get_comments(
    platform: Optional[str] = Query(None, description="Filter by platform"),
    profile_id: Optional[int] = Query(None, description="Filter by profile ID"),
    post_id: Optional[int] = Query(None, description="Filter by post ID"),
    sentiment: Optional[str] = Query(None, description="Filter by sentiment (positive/negative/neutral)"),
    limit: int = Query(100, description="Maximum number of comments"),
    offset: int = Query(0, description="Offset for pagination")
):
    """Get comments with filters."""
    try:
        comments = get_comments_for_dashboard(
            post_id=post_id,
            sentiment=sentiment,
            platform=platform,
            profile_id=profile_id
        )
        
        # Simple pagination
        total = len(comments)
        comments = comments[offset:offset + limit]
        
        return {
            "data": comments,
            "total": total,
            "limit": limit,
            "offset": offset
        }
    except Exception as e:
        logger.error(f"Error getting comments: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# ==================== ANALYSIS ENDPOINTS ====================

@app.post("/api/analysis/run")
def run_analysis(request: AnalysisRequest):
    """Run analysis for profiles."""
    try:
        results = analyze_profiles(profile_ids=request.profile_ids, force=request.force)
        return {
            "success": True,
            "results": results
        }
    except Exception as e:
        logger.error(f"Error running analysis: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# ==================== CONFIG ENDPOINTS ====================

@app.get("/api/config")
def get_config():
    """Get all configuration."""
    try:
        config = get_all_config()
        return config
    except Exception as e:
        logger.error(f"Error getting config: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/config/apify-token")
def update_apify_token(token: str):
    """Update Apify token."""
    try:
        set_apify_token(token)
        return {"success": True, "message": "Token updated successfully"}
    except Exception as e:
        logger.error(f"Error updating token: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/config/actor-id")
def update_actor_id(platform: str, actor_type: str, actor_id: str):
    """Update actor ID for a platform."""
    try:
        set_actor_id(platform, actor_type, actor_id)
        return {"success": True, "message": "Actor ID updated successfully"}
    except Exception as e:
        logger.error(f"Error updating actor ID: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/config/date-from")
def update_date_from(request: DateFromUpdate):
    """Update date filter from for ALL platforms (YYYY-MM-DD format or None)."""
    try:
        set_date_from(request.date_from if request.date_from else None)
        return {"success": True, "message": "Date from updated successfully"}
    except Exception as e:
        logger.error(f"Error updating date from: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/config/date-to")
def update_date_to(request: DateToUpdate):
    """Update date filter to for ALL platforms (YYYY-MM-DD format or None)."""
    try:
        set_date_to(request.date_to if request.date_to else None)
        return {"success": True, "message": "Date to updated successfully"}
    except Exception as e:
        logger.error(f"Error updating date to: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/config/last-days")
def update_last_days(request: LastDaysUpdate):
    """Update last N days filter for ALL platforms (0 = no filter)."""
    try:
        set_last_days(int(request.last_days))
        return {"success": True, "message": "Last days updated successfully"}
    except Exception as e:
        logger.error(f"Error updating last days: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# ==================== STATS ENDPOINTS ====================

@app.get("/api/stats/sentiment")
def get_sentiment_stats_endpoint(
    platform: Optional[str] = Query(None),
    profile_id: Optional[int] = Query(None)
):
    """Get sentiment statistics."""
    try:
        from db_utils import get_sentiment_stats as get_sentiment_stats_db
        stats = get_sentiment_stats_db(platform=platform, profile_id=profile_id)
        
        # Ensure the response format matches what the frontend expects
        return {
            "total": stats.get("total", 0),
            "positive": stats.get("counts", {}).get("POSITIVE", 0),
            "negative": stats.get("counts", {}).get("NEGATIVE", 0),
            "neutral": stats.get("counts", {}).get("NEUTRAL", 0),
            "percentages": stats.get("percentages", {
                "POSITIVE": 0,
                "NEGATIVE": 0,
                "NEUTRAL": 0
            })
        }
    except Exception as e:
        logger.error(f"Error getting sentiment stats: {e}", exc_info=True)
        # Return default values instead of raising error to prevent recursion
        return {
            "total": 0,
            "positive": 0,
            "negative": 0,
            "neutral": 0,
            "percentages": {
                "POSITIVE": 0,
                "NEGATIVE": 0,
                "NEUTRAL": 0
            }
        }

@app.get("/api/stats/overview")
def get_overview_stats(
    platform: Optional[str] = Query(None),
    profile_id: Optional[int] = Query(None),
    date_from: Optional[str] = Query(None),
    date_to: Optional[str] = Query(None)
):
    """Get overview statistics (KPIs)."""
    try:
        date_from_obj = None
        date_to_obj = None
        
        if date_from:
            date_from_obj = datetime.strptime(date_from, "%Y-%m-%d")
        if date_to:
            date_to_obj = datetime.strptime(date_to, "%Y-%m-%d")
        
        posts = get_posts_for_dashboard(
            platform=platform,
            profile_id=profile_id,
            date_from=date_from_obj,
            date_to=date_to_obj
        )
        
        if not posts:
            return {
                "total_posts": 0,
                "total_interactions": 0,
                "total_comments": 0,
                "avg_interactions": 0,
                "platforms": []
            }
        
        total_interactions = sum(p.get("interactions_total", 0) for p in posts)
        
        # Get sentiment stats safely
        try:
            from db_utils import get_sentiment_stats as get_sentiment_stats_db
            sentiment_stats = get_sentiment_stats_db(platform=platform, profile_id=profile_id)
            total_comments = sentiment_stats.get("total", 0)
        except Exception as e:
            logger.warning(f"Error getting sentiment stats: {e}")
            total_comments = 0
        
        avg_interactions = total_interactions / len(posts) if posts else 0
        
        # Group by platform
        platforms = {}
        for post in posts:
            platform_name = post.get("platform", "unknown")
            if platform_name not in platforms:
                platforms[platform_name] = {
                    "platform": platform_name,
                    "posts": 0,
                    "interactions": 0,
                    "comments": 0
                }
            platforms[platform_name]["posts"] += 1
            platforms[platform_name]["interactions"] += post.get("interactions_total", 0)
        
        # Add comment counts per platform (simplified - would need separate query for accuracy)
        from db_utils import get_sentiment_stats as get_sentiment_stats_db
        for platform_name in platforms:
            try:
                platform_sentiment = get_sentiment_stats_db(platform=platform_name, profile_id=profile_id)
                platforms[platform_name]["comments"] = platform_sentiment.get("total", 0)
            except Exception:
                platforms[platform_name]["comments"] = 0
        
        return {
            "total_posts": len(posts),
            "total_interactions": total_interactions,
            "total_comments": total_comments,
            "avg_interactions": round(avg_interactions, 2),
            "platforms": list(platforms.values())
        }
    except Exception as e:
        logger.error(f"Error getting overview stats: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# ==================== APIFY USAGE ENDPOINT ====================

@app.get("/api/apify/usage")
def get_apify_usage():
    """Get Apify account usage information."""
    try:
        scraper = ApifyScraper()
        usage_info = scraper.get_usage_info()
        if not usage_info:
            raise HTTPException(status_code=404, detail="Could not fetch usage info")
        return usage_info
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting Apify usage: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# ==================== HEALTH CHECK ====================

@app.get("/api/health")
def health_check():
    """Health check endpoint."""
    return {"status": "ok", "timestamp": datetime.now().isoformat()}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
