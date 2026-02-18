"""
FastAPI REST API for Social Media Analytics Dashboard.
Provides endpoints for profiles, posts, comments, analysis, and configuration.
"""
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta
import logging
import os

# Import existing modules
from config import (
    ensure_database_initialized, get_all_config, set_apify_token, get_apify_token,
    set_apify_token_facebook_1, get_apify_token_facebook_1,
    set_apify_token_facebook_2, get_apify_token_facebook_2,
    set_apify_token_instagram, get_apify_token_instagram,
    set_apify_token_tiktok, get_apify_token_tiktok,
    set_huggingface_model, get_huggingface_model, set_keywords_positive, get_keywords_positive,
    set_keywords_negative, get_keywords_negative, set_actor_id, get_actor_id,
    set_default_limit_posts, get_default_limit_posts, set_default_limit_comments,
    get_default_limit_comments, set_auto_skip_recent, get_auto_skip_recent,
    set_date_from, get_date_from, set_date_to, get_date_to,
    set_last_days, get_last_days
)
from db_utils import (
    get_all_profiles, add_profile, delete_profile, update_profile_apify_token_key,
    get_posts_for_dashboard, get_comments_for_dashboard, get_sentiment_stats,
    get_most_repeated_comments, get_comments_without_sentiment, update_comment_sentiment,
    export_comments_to_csv, export_posts_to_csv, export_interactions_to_csv
)
from scraper import analyze_profiles, ApifyScraper
from analyzer import reload_analyzer, get_analyzer
from pdf_generator import generate_professional_report
from topic_analyzer import get_top_complaints_by_topic, extract_keywords

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize database
logger.info("Initializing database...")
ensure_database_initialized()
logger.info("Database initialized successfully")

# Create FastAPI app
app = FastAPI(
    title="Social Media Analytics API",
    description="API REST para el dashboard de análisis de redes sociales",
    version="1.0.0"
)

# CORS middleware
# Production frontend URL
PRODUCTION_FRONTEND_URL = "https://frontsocial.vercel.app"

# ngrok URL (backend local con ngrok)
NGROK_URL = "https://www.backsocual.ngrok.app"

# Allowed origins: production frontend + localhost + ngrok for development
default_allowed_origins = [
    PRODUCTION_FRONTEND_URL,
    "http://localhost:3000",
    "http://127.0.0.1:3000",
]

# Agregar ngrok si está configurado
if NGROK_URL:
    default_allowed_origins.append(NGROK_URL)
env_allowed_origins = os.getenv("ALLOWED_ORIGINS")
if env_allowed_origins:
    allowed_origins = [origin.strip() for origin in env_allowed_origins.split(",") if origin.strip()]
else:
    allowed_origins = default_allowed_origins

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
    apify_token_key: Optional[str] = None  # facebook_1, facebook_2, instagram, tiktok

class AnalysisRequest(BaseModel):
    profile_ids: Optional[List[int]] = None
    force: bool = False

class ImportApifyRunRequest(BaseModel):
    run_id: str
    platform: str  # 'instagram' | 'tiktok' | 'facebook'
    profile_id: int

class ImportApifyCommentsRunRequest(BaseModel):
    run_id: str
    platform: str = "facebook"
    profile_id: Optional[int] = None  # opcional: restringe la búsqueda del post a este perfil

class ImportApifyCommentsRunsRequest(BaseModel):
    run_ids: List[str]
    platform: str = "facebook"
    profile_id: Optional[int] = None
    analyze_after: bool = False  # si True, analiza sentimiento de los comentarios importados tras la importación

class ConfigUpdate(BaseModel):
    key: str
    value: Any

class DateFromUpdate(BaseModel):
    date_from: Optional[str] = None

class DateToUpdate(BaseModel):
    date_to: Optional[str] = None

class LastDaysUpdate(BaseModel):
    last_days: int

class LimitPostsUpdate(BaseModel):
    default_limit_posts: int

class LimitCommentsUpdate(BaseModel):
    default_limit_comments: int

class ApifyTokenUpdate(BaseModel):
    apify_token: str

class ApifyTokenKeyUpdate(BaseModel):
    apify_token_facebook_1: Optional[str] = None
    apify_token_facebook_2: Optional[str] = None
    apify_token_instagram: Optional[str] = None
    apify_token_tiktok: Optional[str] = None

class ProfileApifyTokenKeyUpdate(BaseModel):
    apify_token_key: Optional[str] = None  # facebook_1 | facebook_2 | instagram | tiktok | null

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

@app.patch("/api/profiles/{profile_id}/apify-token-key")
def update_profile_apify_token_key_endpoint(profile_id: int, request: ProfileApifyTokenKeyUpdate):
    """Asigna qué API key usa este perfil: facebook_1, facebook_2, instagram, tiktok (o null para auto)."""
    try:
        update_profile_apify_token_key(profile_id, request.apify_token_key)
        return {"success": True, "message": "API key del perfil actualizada"}
    except Exception as e:
        logger.error(f"Error updating profile apify token key: {e}")
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
    except ValueError as e:
        msg = str(e)
        if msg.startswith("APIFY_QUOTA:"):
            logger.warning(f"Apify quota/limit exceeded during analysis: {msg}")
            raise HTTPException(status_code=402, detail=msg.replace("APIFY_QUOTA: ", ""))
        if msg.startswith("APIFY_AUTH:"):
            logger.warning(f"Apify auth error during analysis: {msg}")
            raise HTTPException(status_code=401, detail=msg.replace("APIFY_AUTH: ", ""))
        raise HTTPException(status_code=400, detail=msg)
    except Exception as e:
        logger.error(f"Error running analysis: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/import-apify-run")
def import_apify_run(request: ImportApifyRunRequest):
    """
    Importa posts desde una corrida ya guardada en Apify (sin gastar tokens).
    run_id: ID de la corrida en Apify (Apify Console → Runs → copiar ID).
    platform: instagram | tiktok | facebook
    profile_id: ID del perfil en nuestra BD al que asociar los posts.
    """
    try:
        scraper = ApifyScraper()
        stats = scraper.import_posts_from_apify_run(
            run_id=request.run_id.strip(),
            platform=request.platform.strip().lower(),
            profile_id=request.profile_id,
        )
        return {
            "success": True,
            "message": f"Importados {stats['posts_imported']} posts y {stats['comments_imported']} comentarios",
            "posts_imported": stats["posts_imported"],
            "comments_imported": stats["comments_imported"],
            "errors": stats.get("errors", []),
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error importing from Apify run: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/import-apify-comments-run")
def import_apify_comments_run(request: ImportApifyCommentsRunRequest):
    """
    Importa comentarios desde una corrida de Facebook Comments Scraper.
    La URL del post se obtiene del run en Apify; el post debe existir en la BD (importar posts antes).
    profile_id opcional: si lo pasas, solo se busca el post en ese perfil.
    """
    try:
        scraper = ApifyScraper()
        stats = scraper.import_comments_from_apify_run(
            run_id=request.run_id.strip(),
            platform=request.platform.strip().lower(),
            profile_id=request.profile_id,
        )
        return {
            "success": True,
            "message": f"Importados {stats['comments_imported']} comentarios",
            "comments_imported": stats["comments_imported"],
            "errors": stats.get("errors", []),
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error importing comments from Apify run: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/import-apify-comments-runs")
def import_apify_comments_runs_bulk(request: ImportApifyCommentsRunsRequest):
    """
    Importa comentarios desde varias corridas de Facebook Comments Scraper de una vez.
    run_ids: lista de Run IDs (cada uno = comentarios de un post).
    """
    run_ids = [r.strip() for r in request.run_ids if r and r.strip()]
    if not run_ids:
        raise HTTPException(status_code=400, detail="run_ids no puede estar vacío")
    try:
        scraper = ApifyScraper()
        total_comments = 0
        ok = 0
        failed = []
        for run_id in run_ids:
            try:
                stats = scraper.import_comments_from_apify_run(
                    run_id=run_id,
                    platform=request.platform.strip().lower(),
                    profile_id=request.profile_id,
                )
                total_comments += stats.get("comments_imported", 0)
                ok += 1
            except Exception as e:
                failed.append({"run_id": run_id, "error": str(e)})
        resp = {
            "success": True,
            "message": f"Importados {total_comments} comentarios en {ok}/{len(run_ids)} corridas",
            "runs_ok": ok,
            "runs_failed": len(failed),
            "total_comments_imported": total_comments,
            "failed": failed[:20],
        }
        if request.analyze_after and total_comments:
            try:
                pending = get_comments_without_sentiment(
                    profile_id=request.profile_id,
                    platform=request.platform.strip().lower(),
                    limit=None
                )
                analyzer = get_analyzer()
                analyzed = 0
                for row in pending:
                    try:
                        text = (row.get("text") or "").strip()
                        if not text:
                            continue
                        result = analyzer.analyze(text)
                        update_comment_sentiment(
                            comment_id_internal=row["id"],
                            sentiment_label=result["label"],
                            sentiment_score=result["score"],
                            sentiment_method=result["method"],
                        )
                        analyzed += 1
                    except Exception as e:
                        logger.warning(f"Error analizando comentario id={row.get('id')}: {e}")
                resp["analyzed_after_import"] = analyzed
                if analyzed:
                    resp["message"] = resp["message"] + f" Analizados {analyzed} comentarios para el dashboard."
                else:
                    resp["message"] = resp["message"] + " Los comentarios ya tenían sentimiento (se analizan al importar)."
            except Exception as e:
                logger.warning(f"Error analizando comentarios tras importación: {e}")
                resp["analyzed_after_import"] = 0
                resp["analyze_after_error"] = str(e)
        return resp
    except Exception as e:
        logger.error(f"Error en importación masiva: {e}")
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
def update_apify_token(request: ApifyTokenUpdate):
    """Update Apify token (por defecto / fallback)."""
    try:
        set_apify_token(request.apify_token)
        return {"success": True, "message": "Token actualizado"}
    except Exception as e:
        logger.error(f"Error updating token: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/config/apify-tokens-by-platform")
def update_apify_tokens_by_platform(request: ApifyTokenKeyUpdate):
    """Actualiza los tokens por plataforma: Facebook 1, Facebook 2, Instagram, TikTok."""
    try:
        if request.apify_token_facebook_1 is not None:
            set_apify_token_facebook_1(request.apify_token_facebook_1)
        if request.apify_token_facebook_2 is not None:
            set_apify_token_facebook_2(request.apify_token_facebook_2)
        if request.apify_token_instagram is not None:
            set_apify_token_instagram(request.apify_token_instagram)
        if request.apify_token_tiktok is not None:
            set_apify_token_tiktok(request.apify_token_tiktok)
        return {"success": True, "message": "Tokens por plataforma actualizados"}
    except Exception as e:
        logger.error(f"Error updating apify tokens: {e}")
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

@app.post("/api/config/limit-posts")
def update_limit_posts(request: LimitPostsUpdate):
    """Update default max number of posts to scrape per profile."""
    try:
        set_default_limit_posts(max(1, int(request.default_limit_posts)))
        return {"success": True, "message": "Límite de publicaciones actualizado"}
    except Exception as e:
        logger.error(f"Error updating limit posts: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/config/limit-comments")
def update_limit_comments(request: LimitCommentsUpdate):
    """Update default max number of comments per post to scrape."""
    try:
        set_default_limit_comments(max(1, int(request.default_limit_comments)))
        return {"success": True, "message": "Límite de comentarios actualizado"}
    except Exception as e:
        logger.error(f"Error updating limit comments: {e}")
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

# ==================== ROOT ENDPOINT ====================

@app.get("/")
def root():
    """Root endpoint - redirect to API docs."""
    return {
        "message": "Social Media Analytics API",
        "version": "1.0.0",
        "docs": "/docs",
        "health": "/api/health"
    }

# ==================== MOST REPEATED COMMENTS ENDPOINT ====================

@app.get("/api/comments/most-repeated")
def get_most_repeated_comments_endpoint(
    profile_id: Optional[int] = Query(None, description="ID del perfil a analizar"),
    platform: Optional[str] = Query(None, description="Plataforma específica (opcional)"),
    limit: int = Query(10, description="Número máximo de comentarios a retornar")
):
    """Obtiene los comentarios más repetidos."""
    try:
        comments = get_most_repeated_comments(
            profile_id=profile_id,
            platform=platform,
            limit=limit
        )
        return {
            "data": comments,
            "total": len(comments)
        }
    except Exception as e:
        logger.error(f"Error obteniendo comentarios más repetidos: {e}")
        raise HTTPException(status_code=500, detail=f"Error obteniendo comentarios: {str(e)}")


@app.get("/api/comments/top-complaints")
def get_top_complaints_endpoint(
    profile_id: Optional[int] = Query(None, description="ID del perfil a analizar"),
    platform: Optional[str] = Query(None, description="Plataforma específica (opcional)"),
    limit: int = Query(5, description="Número de temas a retornar")
):
    """Obtiene los top reclamos agrupados por tema con palabras clave."""
    try:
        logger.info(f"Obteniendo top complaints - profile_id: {profile_id}, platform: {platform}, limit: {limit}")
        
        # Obtener todos los comentarios
        all_comments = get_comments_for_dashboard(
            profile_id=profile_id,
            platform=platform,
            sentiment=None
        )
        
        logger.info(f"Total de comentarios obtenidos: {len(all_comments)}")
        
        # Convertir a formato para análisis de temas
        comments_for_analysis = [
            {
                "text": c.get("text", ""),
                "id": c.get("id"),
                "likes": c.get("likes", 0),
                "sentiment_label": c.get("sentiment_label"),
                "platform": c.get("platform")
            }
            for c in all_comments
            if c.get("text")
        ]
        
        logger.info(f"Comentarios para análisis: {len(comments_for_analysis)}")
        
        # Analizar y agrupar por temas
        top_complaints = get_top_complaints_by_topic(comments_for_analysis, top_n=limit)
        
        logger.info(f"Top complaints encontrados: {len(top_complaints)}")
        
        return {
            "data": top_complaints,
            "total": len(top_complaints)
        }
    except Exception as e:
        logger.error(f"Error obteniendo top reclamos: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error obteniendo reclamos: {str(e)}")


@app.post("/api/comments/analyze-pending")
def analyze_pending_comments_endpoint(
    profile_id: Optional[int] = Query(None, description="ID del perfil (opcional)"),
    platform: Optional[str] = Query(None, description="Plataforma (opcional)"),
    limit: Optional[int] = Query(None, description="Máximo de comentarios a analizar (opcional, sin límite por defecto)")
):
    """
    Analiza el sentimiento de todos los comentarios que aún no tienen análisis.
    Así los comentarios importados (ej. desde Apify) pasan a contarse en el dashboard.
    """
    try:
        pending = get_comments_without_sentiment(
            profile_id=profile_id,
            platform=platform,
            limit=limit
        )
        if not pending:
            return {
                "success": True,
                "message": "No hay comentarios pendientes de analizar.",
                "analyzed": 0,
                "errors": []
            }
        analyzer = get_analyzer()
        analyzed = 0
        errors = []
        for row in pending:
            try:
                text = (row.get("text") or "").strip()
                if not text:
                    continue
                result = analyzer.analyze(text)
                update_comment_sentiment(
                    comment_id_internal=row["id"],
                    sentiment_label=result["label"],
                    sentiment_score=result["score"],
                    sentiment_method=result["method"]
                )
                analyzed += 1
            except Exception as e:
                logger.warning(f"Error analizando comentario id={row.get('id')}: {e}")
                errors.append(str(e))
        logger.info(f"Analizados {analyzed} comentarios pendientes (errores: {len(errors)})")
        return {
            "success": True,
            "message": f"Se analizaron {analyzed} comentarios. Ya aparecerán en el resumen del dashboard.",
            "analyzed": analyzed,
            "pending_before": len(pending),
            "errors": errors[:20]
        }
    except Exception as e:
        logger.error(f"Error analizando comentarios pendientes: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/comments/process-all")
def process_all_comments_endpoint(
    profile_id: Optional[int] = Query(None, description="ID del perfil a procesar (opcional)"),
    platform: Optional[str] = Query(None, description="Plataforma específica (opcional)")
):
    """
    Procesa todos los comentarios existentes en la BD para análisis de temas.
    Esto analiza comentarios que ya están guardados sin necesidad de hacer scraping.
    """
    try:
        # Obtener todos los comentarios
        all_comments = get_comments_for_dashboard(
            profile_id=profile_id,
            platform=platform,
            sentiment=None
        )
        
        total_processed = len(all_comments)
        
        logger.info(f"Procesando {total_processed} comentarios existentes para análisis de temas...")
        
        # Los comentarios ya están en la BD, solo necesitamos retornar que están listos
        # El análisis de temas se hace al llamar a get_top_complaints_endpoint
        
        return {
            "success": True,
            "message": f"Se encontraron {total_processed} comentarios en la base de datos. Los temas se calculan automáticamente al consultar /api/comments/top-complaints",
            "total_comments": total_processed
        }
    except Exception as e:
        logger.error(f"Error procesando comentarios: {e}")
        raise HTTPException(status_code=500, detail=f"Error procesando comentarios: {str(e)}")

# ==================== PDF REPORT ENDPOINT ====================

@app.get("/api/report/pdf")
def generate_pdf_report(
    profile_id: Optional[int] = Query(None, description="ID del perfil a analizar (opcional, si hay múltiples usar profile_ids)"),
    profile_ids: Optional[str] = Query(None, description="IDs de perfiles separados por coma (ej: '1,2,3')"),
    platform: Optional[str] = Query(None, description="Plataforma específica (opcional)"),
    days: int = Query(7, description="Últimos N días para el análisis")
):
    """Genera un reporte PDF profesional del análisis."""
    try:
        # Obtener datos del perfil
        profiles = get_all_profiles()
        if not profiles:
            raise HTTPException(status_code=404, detail="No se encontraron perfiles")
        
        # Determinar qué perfiles incluir
        selected_profile_ids = []
        if profile_ids:
            # Múltiples perfiles especificados
            try:
                selected_profile_ids = [int(pid.strip()) for pid in profile_ids.split(',')]
            except ValueError:
                raise HTTPException(status_code=400, detail="profile_ids debe ser una lista de números separados por coma")
        elif profile_id:
            # Un solo perfil
            selected_profile_ids = [profile_id]
        else:
            # Todos los perfiles
            selected_profile_ids = [p.get('id') for p in profiles]
        
        # Filtrar perfiles válidos
        valid_profiles = [p for p in profiles if p.get('id') in selected_profile_ids]
        if not valid_profiles:
            raise HTTPException(status_code=404, detail="No se encontraron perfiles válidos")
        
        # Construir nombre del reporte
        if len(valid_profiles) == 1:
            profile = valid_profiles[0]
            profile_name = profile.get('display_name') or profile.get('username_or_url', 'Perfil Desconocido')
        else:
            # Múltiples perfiles
            profile_names = [p.get('display_name') or p.get('username_or_url', '') for p in valid_profiles]
            profile_name = f"Múltiples Perfiles ({len(valid_profiles)})"
        
        # Calcular rango de fechas
        date_to = datetime.now()
        date_from = date_to - timedelta(days=days)
        date_range = f"{date_from.strftime('%d/%m/%Y')} - {date_to.strftime('%d/%m/%Y')}"
        
        # Combinar estadísticas de todos los perfiles seleccionados
        all_posts = []
        all_comments = []
        combined_sentiment_counts = {"POSITIVE": 0, "NEGATIVE": 0, "NEUTRAL": 0}
        
        for pid in selected_profile_ids:
            # Obtener posts
            profile_posts = get_posts_for_dashboard(profile_id=pid, platform=platform)
            all_posts.extend(profile_posts)
            
            # Obtener comentarios
            profile_comments = get_comments_for_dashboard(
                profile_id=pid,
                platform=platform,
                sentiment=None
            )
            all_comments.extend(profile_comments)
            
            # Combinar sentimientos
            profile_sentiment = get_sentiment_stats(profile_id=pid, platform=platform)
            counts = profile_sentiment.get('counts', {})
            combined_sentiment_counts['POSITIVE'] += counts.get('POSITIVE', 0)
            combined_sentiment_counts['NEGATIVE'] += counts.get('NEGATIVE', 0)
            combined_sentiment_counts['NEUTRAL'] += counts.get('NEUTRAL', 0)
        
        # Calcular porcentajes combinados
        total_sentiment = sum(combined_sentiment_counts.values())
        sentiment_percentages = {}
        if total_sentiment > 0:
            sentiment_percentages = {
                'POSITIVE': (combined_sentiment_counts['POSITIVE'] / total_sentiment) * 100,
                'NEGATIVE': (combined_sentiment_counts['NEGATIVE'] / total_sentiment) * 100,
                'NEUTRAL': (combined_sentiment_counts['NEUTRAL'] / total_sentiment) * 100
            }
        
        sentiment_stats = {
            'counts': combined_sentiment_counts,
            'percentages': sentiment_percentages,
            'total': total_sentiment
        }
        
        # Obtener estadísticas por plataforma
        platform_stats = {}
        all_platforms = set()
        
        for post in all_posts:
            platform_name = post.get('platform', 'unknown')
            all_platforms.add(platform_name)
        
        # Calcular estadísticas por plataforma
        for platform_name in all_platforms:
            platform_posts = [p for p in all_posts if p.get('platform') == platform_name]
            platform_comments = [c for c in all_comments if c.get('platform') == platform_name]
            
            # Calcular sentimiento por plataforma
            platform_sentiment_counts = {"POSITIVE": 0, "NEGATIVE": 0, "NEUTRAL": 0}
            for comment in platform_comments:
                sentiment = comment.get('sentiment_label')
                if sentiment in platform_sentiment_counts:
                    platform_sentiment_counts[sentiment] += 1
            
            platform_total = sum(platform_sentiment_counts.values())
            platform_percentages = {}
            if platform_total > 0:
                platform_percentages = {
                    'POSITIVE': (platform_sentiment_counts['POSITIVE'] / platform_total) * 100,
                    'NEGATIVE': (platform_sentiment_counts['NEGATIVE'] / platform_total) * 100,
                    'NEUTRAL': (platform_sentiment_counts['NEUTRAL'] / platform_total) * 100
                }
            
            platform_stats[platform_name] = {
                'posts': len(platform_posts),
                'comments': len(platform_comments),
                'sentiment': platform_percentages
            }
        
        # Obtener comentarios más repetidos (combinar de todos los perfiles seleccionados)
        # Para múltiples perfiles, obtener de todos y combinar
        if len(selected_profile_ids) == 1:
            most_repeated = get_most_repeated_comments(
                profile_id=selected_profile_ids[0],
                platform=platform,
                limit=10
            )
        else:
            # Múltiples perfiles: obtener comentarios de todos y agrupar
            from collections import defaultdict
            comment_groups = defaultdict(lambda: {
                'text': '',
                'count': 0,
                'total_likes': 0,
                'most_common_sentiment': None
            })
            
            for pid in selected_profile_ids:
                profile_repeated = get_most_repeated_comments(
                    profile_id=pid,
                    platform=platform,
                    limit=20
                )
                for comment in profile_repeated:
                    text = comment.get('text', '').lower().strip()
                    if text:
                        if not comment_groups[text]['text']:
                            comment_groups[text]['text'] = comment.get('text', '')
                        comment_groups[text]['count'] += comment.get('count', 0)
                        comment_groups[text]['total_likes'] += comment.get('total_likes', 0)
                        if not comment_groups[text]['most_common_sentiment']:
                            comment_groups[text]['most_common_sentiment'] = comment.get('most_common_sentiment')
            
            # Convertir a lista y ordenar
            most_repeated = sorted(
                [
                    {
                        'text': c['text'],
                        'count': c['count'],
                        'total_likes': c['total_likes'],
                        'most_common_sentiment': c['most_common_sentiment']
                    }
                    for c in comment_groups.values()
                ],
                key=lambda x: x['count'],
                reverse=True
            )[:10]
        
        # Obtener top complaints por tema
        try:
            comments_for_analysis = [
                {
                    "text": c.get("text", ""),
                    "id": c.get("id"),
                    "likes": c.get("likes", 0),
                    "sentiment_label": c.get("sentiment_label"),
                    "platform": c.get("platform")
                }
                for c in all_comments
                if c.get("text")
            ]
            top_complaints = get_top_complaints_by_topic(comments_for_analysis, top_n=5)
        except Exception as e:
            logger.warning(f"Error obteniendo top complaints para PDF: {e}")
            top_complaints = []
        
        # Contar totales
        total_posts = len(all_posts)
        total_comments = len(all_comments)
        
        # Generar PDF
        pdf_content = generate_professional_report(
            profile_name=profile_name,
            sentiment_stats=sentiment_stats,
            platform_stats=platform_stats,
            most_repeated_comments=most_repeated,
            total_posts=total_posts,
            total_comments=total_comments,
            date_range=date_range,
            top_complaints=top_complaints if top_complaints else None
        )
        
        # Retornar PDF como respuesta
        return Response(
            content=pdf_content,
            media_type="application/pdf",
            headers={
                "Content-Disposition": f"attachment; filename=reporte_{profile_name.replace(' ', '_')}_{datetime.now().strftime('%Y%m%d')}.pdf"
            }
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error generando reporte PDF: {e}")
        raise HTTPException(status_code=500, detail=f"Error generando reporte: {str(e)}")

# ==================== HEALTH CHECK ====================

# ==================== CSV EXPORT ====================

@app.get("/api/export/comments")
def export_comments(
    profile_id: Optional[List[int]] = Query(None, description="ID del perfil (puede ser múltiple)"),
    platform: Optional[str] = Query(None, description="Plataforma (facebook, instagram, tiktok)"),
    sentiment: Optional[str] = Query(None, description="Sentimiento (POSITIVE, NEGATIVE, NEUTRAL)"),
    date_from: Optional[str] = Query(None, description="Fecha desde (YYYY-MM-DD)"),
    date_to: Optional[str] = Query(None, description="Fecha hasta (YYYY-MM-DD)")
):
    """Export comments to CSV."""
    try:
        # Parse dates (only if provided)
        date_from_obj = None
        date_to_obj = None
        if date_from:
            date_from_obj = datetime.fromisoformat(date_from)
        if date_to:
            date_to_obj = datetime.fromisoformat(date_to)
        
        # Handle multiple profile IDs
        profile_ids = profile_id if isinstance(profile_id, list) else ([profile_id] if profile_id else None)
        
        # If multiple profiles, combine results
        if profile_ids and len(profile_ids) > 1:
            all_comments = []
            for pid in profile_ids:
                csv_content = export_comments_to_csv(
                    profile_id=pid,
                    platform=platform,
                    sentiment_label=sentiment,
                    date_from=date_from_obj,
                    date_to=date_to_obj
                )
                # Parse CSV and combine (skip header after first)
                lines = csv_content.strip().split('\n')
                if all_comments:
                    all_comments.extend(lines[1:])  # Skip header
                else:
                    all_comments.extend(lines)
            csv_content = '\n'.join(all_comments)
        else:
            # Single profile or no profile filter
            single_profile_id = profile_ids[0] if profile_ids else None
            csv_content = export_comments_to_csv(
                profile_id=single_profile_id,
                platform=platform,
                sentiment_label=sentiment,
                date_from=date_from_obj,
                date_to=date_to_obj
            )
        
        # Generate filename
        filename_parts = ['comentarios']
        if profile_ids:
            if len(profile_ids) == 1:
                filename_parts.append(f'perfil_{profile_ids[0]}')
            else:
                filename_parts.append(f'{len(profile_ids)}_perfiles')
        if platform:
            filename_parts.append(platform)
        if date_from:
            filename_parts.append(date_from)
        if date_to:
            filename_parts.append(date_to)
        filename = '_'.join(filename_parts) + '.csv'
        
        return Response(
            content=csv_content,
            media_type="text/csv",
            headers={
                "Content-Disposition": f"attachment; filename={filename}"
            }
        )
    except Exception as e:
        logger.error(f"Error exportando comentarios: {e}")
        raise HTTPException(status_code=500, detail=f"Error exportando comentarios: {str(e)}")


@app.get("/api/export/posts")
def export_posts(
    profile_id: Optional[List[int]] = Query(None, description="ID del perfil (puede ser múltiple)"),
    platform: Optional[str] = Query(None, description="Plataforma (facebook, instagram, tiktok)"),
    date_from: Optional[str] = Query(None, description="Fecha desde (YYYY-MM-DD)"),
    date_to: Optional[str] = Query(None, description="Fecha hasta (YYYY-MM-DD)")
):
    """Export posts to CSV."""
    try:
        # Parse dates (only if provided)
        date_from_obj = None
        date_to_obj = None
        if date_from:
            date_from_obj = datetime.fromisoformat(date_from)
        if date_to:
            date_to_obj = datetime.fromisoformat(date_to)
        
        # Handle multiple profile IDs
        profile_ids = profile_id if isinstance(profile_id, list) else ([profile_id] if profile_id else None)
        
        # If multiple profiles, combine results
        if profile_ids and len(profile_ids) > 1:
            all_posts = []
            for pid in profile_ids:
                csv_content = export_posts_to_csv(
                    profile_id=pid,
                    platform=platform,
                    date_from=date_from_obj,
                    date_to=date_to_obj
                )
                # Parse CSV and combine (skip header after first)
                lines = csv_content.strip().split('\n')
                if all_posts:
                    all_posts.extend(lines[1:])  # Skip header
                else:
                    all_posts.extend(lines)
            csv_content = '\n'.join(all_posts)
        else:
            # Single profile or no profile filter
            single_profile_id = profile_ids[0] if profile_ids else None
            csv_content = export_posts_to_csv(
                profile_id=single_profile_id,
                platform=platform,
                date_from=date_from_obj,
                date_to=date_to_obj
            )
        
        # Generate filename
        filename_parts = ['posts']
        if profile_ids:
            if len(profile_ids) == 1:
                filename_parts.append(f'perfil_{profile_ids[0]}')
            else:
                filename_parts.append(f'{len(profile_ids)}_perfiles')
        if platform:
            filename_parts.append(platform)
        if date_from:
            filename_parts.append(date_from)
        if date_to:
            filename_parts.append(date_to)
        filename = '_'.join(filename_parts) + '.csv'
        
        return Response(
            content=csv_content,
            media_type="text/csv",
            headers={
                "Content-Disposition": f"attachment; filename={filename}"
            }
        )
    except Exception as e:
        logger.error(f"Error exportando posts: {e}")
        raise HTTPException(status_code=500, detail=f"Error exportando posts: {str(e)}")


@app.get("/api/export/interactions")
def export_interactions(
    profile_id: Optional[List[int]] = Query(None, description="ID del perfil (puede ser múltiple)"),
    platform: Optional[str] = Query(None, description="Plataforma (facebook, instagram, tiktok)"),
    date_from: Optional[str] = Query(None, description="Fecha desde (YYYY-MM-DD)"),
    date_to: Optional[str] = Query(None, description="Fecha hasta (YYYY-MM-DD)")
):
    """Export interaction statistics to CSV (aggregated by day)."""
    try:
        # Parse dates (only if provided)
        date_from_obj = None
        date_to_obj = None
        if date_from:
            date_from_obj = datetime.fromisoformat(date_from)
        if date_to:
            date_to_obj = datetime.fromisoformat(date_to)
        
        # Handle multiple profile IDs
        profile_ids = profile_id if isinstance(profile_id, list) else ([profile_id] if profile_id else None)
        
        # If multiple profiles, combine results
        if profile_ids and len(profile_ids) > 1:
            all_interactions = {}
            for pid in profile_ids:
                csv_content = export_interactions_to_csv(
                    profile_id=pid,
                    platform=platform,
                    date_from=date_from_obj,
                    date_to=date_to_obj
                )
                # Parse CSV and combine by date
                lines = csv_content.strip().split('\n')
                header = lines[0]
                for line in lines[1:]:
                    parts = line.split(',')
                    if len(parts) >= 2:
                        date_key = parts[0]
                        if date_key not in all_interactions:
                            all_interactions[date_key] = [0] * (len(parts) - 1)
                        for i in range(1, len(parts)):
                            try:
                                all_interactions[date_key][i-1] += int(parts[i]) if parts[i] else 0
                            except:
                                pass
            
            # Rebuild CSV
            csv_lines = [header]
            for date_key in sorted(all_interactions.keys()):
                csv_lines.append(f"{date_key},{','.join(map(str, all_interactions[date_key]))}")
            csv_content = '\n'.join(csv_lines)
        else:
            # Single profile or no profile filter
            single_profile_id = profile_ids[0] if profile_ids else None
            csv_content = export_interactions_to_csv(
                profile_id=single_profile_id,
                platform=platform,
                date_from=date_from_obj,
                date_to=date_to_obj
            )
        
        # Generate filename
        filename_parts = ['interacciones']
        if profile_ids:
            if len(profile_ids) == 1:
                filename_parts.append(f'perfil_{profile_ids[0]}')
            else:
                filename_parts.append(f'{len(profile_ids)}_perfiles')
        if platform:
            filename_parts.append(platform)
        if date_from:
            filename_parts.append(date_from)
        if date_to:
            filename_parts.append(date_to)
        filename = '_'.join(filename_parts) + '.csv'
        
        return Response(
            content=csv_content,
            media_type="text/csv",
            headers={
                "Content-Disposition": f"attachment; filename={filename}"
            }
        )
    except Exception as e:
        logger.error(f"Error exportando interacciones: {e}")
        raise HTTPException(status_code=500, detail=f"Error exportando interacciones: {str(e)}")


# ==================== HEALTH CHECK ====================

@app.get("/api/health")
def health_check():
    """Health check endpoint."""
    return {"status": "ok", "timestamp": datetime.now().isoformat()}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
