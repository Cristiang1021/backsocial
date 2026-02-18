"""
Web scraping module using Apify actors.
Handles scraping posts and comments from Instagram, TikTok, and Facebook.
"""
import hashlib
import logging
from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta
import requests
from apify_client import ApifyClient
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

from config import (
    get_apify_token, get_apify_token_for_profile, get_actor_id, get_default_limit_posts,
    get_default_limit_comments, get_auto_skip_recent,
    get_date_from, get_date_to, get_last_days
)
from db_utils import (
    get_all_profiles, update_profile_last_analyzed, insert_post, insert_comment,
    get_post_profile_and_platform,
)
from utils import normalize_username_or_url, clean_text
from analyzer import get_analyzer

logger = logging.getLogger(__name__)


class ApifyScraper:
    """Scraper for social media platforms using Apify actors."""
    
    def __init__(self):
        self.token = get_apify_token()
        self.client = None
        if self.token:
            try:
                self.client = ApifyClient(self.token)
            except Exception as e:
                logger.error(f"Error initializing Apify client: {e}")
    
    def _ensure_client(self) -> bool:
        """Ensure Apify client is initialized."""
        if not self.token:
            raise ValueError("Apify token not configured. Please set it in Configuration page.")
        
        if not self.client:
            try:
                self.client = ApifyClient(self.token)
            except Exception as e:
                raise ValueError(f"Invalid Apify token: {e}. Please check your token in Configuration.")
        
        return True
    
    def get_usage_info(self) -> Optional[Dict[str, Any]]:
        """Get Apify account usage information."""
        if not self._ensure_client():
            return None
        
        try:
            # Get user info
            user = self.client.user().get()
            username = user.get("username", "N/A")
            plan_info = user.get("plan", {})
            plan_name = plan_info.get("name", "Free")
            
            # Try to get usage stats (may not be available in all API versions)
            usage_info = {
                "username": username,
                "plan": plan_name,
                "usage_url": f"https://console.apify.com/account/usage"
            }
            
            # Try to get account limits if available
            if "limits" in user:
                usage_info["limits"] = user.get("limits", {})
            
            return usage_info
        except Exception as e:
            logger.warning(f"Could not fetch Apify usage info: {e}")
            return None
    
    def _client_for_token(self, token: Optional[str] = None):
        """Devuelve un cliente Apify para el token dado, o self.client si no se pasa token."""
        if token and token.strip():
            return ApifyClient(token.strip())
        self._ensure_client()
        return self.client

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        retry=retry_if_exception_type((ConnectionError, TimeoutError))
    )
    def _run_actor(self, actor_id: str, input_data: Dict[str, Any], token: Optional[str] = None) -> Dict[str, Any]:
        """Run an Apify actor with retry logic.
        Si se pasa token, se usa ese token (ej. por perfil); si no, el del scraper.
        Raises ValueError with message that may include APIFY_QUOTA or APIFY_AUTH for the API to show a clear message.
        """
        client = self._client_for_token(token)
        try:
            run = client.actor(actor_id).call(run_input=input_data)
            return run
        except Exception as e:
            err_msg = str(e).lower()
            logger.error(f"Error running actor {actor_id}: {e}")
            if "unauthorized" in err_msg or "401" in err_msg or ("token" in err_msg and "invalid" in err_msg):
                raise ValueError("APIFY_AUTH: Token de Apify inválido o no configurado. Ve a Configuración → API & Tokens, guarda un token válido y vuelve a ejecutar el análisis.")
            if "402" in err_msg or "payment" in err_msg or "quota" in err_msg or "credit" in err_msg or "429" in err_msg or "rate limit" in err_msg or "limit exceeded" in err_msg:
                raise ValueError("APIFY_QUOTA: Se acabó la cuota de Apify o se superó el límite. Puedes pausar, configurar otro token en Configuración → API & Tokens, y volver a ejecutar el análisis.")
            if "token" in err_msg:
                raise ValueError(f"APIFY_AUTH: Error con el token de Apify: {e}. Revisa Configuración → API & Tokens.")
            raise
    
    def _get_actor_dataset(self, run: Dict[str, Any], client: Optional[Any] = None) -> List[Dict[str, Any]]:
        """Get dataset items from an Apify actor run. Si se pasó client (por token), usarlo."""
        if not run or "defaultDatasetId" not in run:
            return []
        c = client or self.client
        if not c:
            self._ensure_client()
            c = self.client
        dataset_id = run["defaultDatasetId"]
        items = []
        try:
            for item in c.dataset(dataset_id).iterate_items():
                items.append(item)
        except Exception as e:
            logger.error(f"Error fetching dataset items: {e}")
        return items

    def get_dataset_from_run_id(self, run_id: str) -> List[Dict[str, Any]]:
        """
        Recupera el dataset de una corrida ya ejecutada en Apify (sin gastar tokens).
        run_id: ID de la corrida (ej. el que ves en Apify Console → Runs).
        """
        if not self._ensure_client():
            return []
        try:
            run = self.client.run(run_id).get()
            return self._get_actor_dataset(run)
        except Exception as e:
            logger.error(f"Error recuperando run {run_id} de Apify: {e}")
            raise ValueError(f"No se pudo recuperar la corrida: {e}. Comprueba el run_id y que la corrida sea tuya.")

    def import_posts_from_apify_run(
        self,
        run_id: str,
        platform: str,
        profile_id: int,
    ) -> Dict[str, Any]:
        """
        Importa posts (y comentarios embebidos) desde una corrida guardada en Apify.
        No ejecuta el actor ni gasta tokens; solo descarga el dataset y lo guarda en nuestra BD.
        """
        from db_utils import get_profile_by_id
        profile = get_profile_by_id(profile_id)
        if not profile:
            raise ValueError(f"Perfil {profile_id} no encontrado")
        username = profile.get("username_or_url", "")
        logger.info(f"Importando desde run Apify {run_id} para {platform} / {username} (profile_id={profile_id})")
        items = self.get_dataset_from_run_id(run_id)
        if not items:
            return {"posts_imported": 0, "comments_imported": 0, "errors": ["Dataset vacío o run no encontrado"]}
        stats = {"posts_imported": 0, "comments_imported": 0, "errors": []}
        for idx, post_item in enumerate(items):
            try:
                post_db_id = self.process_post_item(post_item, platform, profile_id)
                if not post_db_id:
                    continue
                stats["posts_imported"] += 1
                comments_list = []
                for field in ["_embedded_comments", "commentsData", "topComments", "commentsList", "comments"]:
                    if field in post_item and isinstance(post_item.get(field), list):
                        comments_list = post_item[field]
                        break
                if comments_list:
                    for comment_item in comments_list:
                        self.process_comment_item(comment_item, post_db_id)
                    stats["comments_imported"] += len(comments_list)
            except Exception as e:
                logger.warning(f"Error procesando item {idx+1}: {e}")
                stats["errors"].append(str(e))
        update_profile_last_analyzed(profile_id)
        logger.info(f"Importación desde run {run_id}: {stats['posts_imported']} posts, {stats['comments_imported']} comentarios")
        return stats

    def import_comments_from_apify_run(
        self,
        run_id: str,
        platform: str = "facebook",
        profile_id: Optional[int] = None,
    ) -> Dict[str, Any]:
        """
        Importa comentarios desde una corrida de Facebook Comments Scraper (u otro actor de comentarios).
        Obtiene la URL del post desde el input del run, busca el post en nuestra BD y asocia los comentarios.
        """
        from db_utils import get_post_by_url
        if not self._ensure_client():
            return {"comments_imported": 0, "errors": ["Cliente Apify no disponible"]}
        try:
            run = self.client.run(run_id).get()
        except Exception as e:
            logger.error(f"Error recuperando run {run_id}: {e}")
            raise ValueError(f"No se pudo recuperar la corrida: {e}")
        # URL del post: primero desde input del run (startUrls), si no desde el primer ítem del dataset (facebookUrl)
        post_url = None
        inp = run.get("input") or run.get("options") or {}
        start_urls = inp.get("startUrls") or inp.get("directUrls") or []
        if isinstance(start_urls, list) and start_urls:
            first = start_urls[0]
            post_url = first.get("url") if isinstance(first, dict) else (first if isinstance(first, str) else None)
        items = self._get_actor_dataset(run)
        if not post_url and items:
            first_item = items[0] if isinstance(items[0], dict) else None
            if first_item:
                post_url = first_item.get("facebookUrl") or first_item.get("url") or first_item.get("postUrl")
        if not post_url:
            # Corrida sin comentarios (dataset vacío): no es error, devolver 0 importados
            if not items:
                return {"comments_imported": 0, "errors": []}
            raise ValueError("No se encontró la URL del post (ni en input del run ni en ítems del dataset con facebookUrl)")
        post_row = get_post_by_url(post_url, profile_id)
        if not post_row:
            raise ValueError(f"No hay ningún post en la BD con la URL de esta corrida. Importa primero los posts (run de Facebook Posts Scraper) o verifica profile_id. URL: {post_url[:80]}...")
        post_db_id = post_row["id"]
        if not items:
            return {"comments_imported": 0, "post_url": post_url[:60], "errors": []}
        stats = {"comments_imported": 0, "errors": []}
        for item in items:
            try:
                self.process_comment_item(item, post_db_id)
                stats["comments_imported"] += 1
            except Exception as e:
                logger.warning(f"Error procesando comentario: {e}")
                stats["errors"].append(str(e))
        logger.info(f"Importados {stats['comments_imported']} comentarios desde run {run_id} para post {post_url[:50]}...")
        return stats

    def _filter_posts_by_date(self, items: List[Dict[str, Any]], platform: str) -> List[Dict[str, Any]]:
        """
        Filter posts by date manually for TikTok and Instagram.
        This is done after getting results from the actor because:
        - TikTok actor's date filter is too aggressive and discards too many videos
        - Instagram actor doesn't support date filters
        """
        from config import get_last_days, get_date_from, get_date_to
        
        last_days = get_last_days()
        date_from_str = get_date_from()
        date_to_str = get_date_to()
        
        # If no filters configured, return all items
        if (not last_days or last_days == 0) and not date_from_str and not date_to_str:
            logger.info(f"No date filters configured for {platform}, returning all posts")
            return items
        
        # Prioridad: si el usuario eligió fechas específicas (desde/hasta), solo esas cuentan; si no, últimos N días.
        today = datetime.now().date()
        date_from = None
        date_to = None
        use_specific_dates = bool(date_from_str or date_to_str)
        
        if use_specific_dates:
            if date_from_str:
                try:
                    date_from = datetime.strptime(date_from_str, "%Y-%m-%d").date()
                except Exception:
                    pass
            if date_to_str:
                try:
                    date_to = datetime.strptime(date_to_str, "%Y-%m-%d").date()
                except Exception:
                    pass
            if date_from or date_to:
                logger.info(f"Filtering {platform} posts: fechas específicas from {date_from} to {date_to}")
        elif last_days and last_days > 0:
            date_from = today - timedelta(days=last_days)
            date_to = today - timedelta(days=1)
            logger.info(f"Filtering {platform} posts: last {last_days} days (from {date_from} to {date_to}, excl. today)")
        
        if not date_from and not date_to:
            return items
        
        # Filter items by date
        filtered_items = []
        for item in items:
            post_date = None
            
            # Try to extract post date from various fields (platform-specific)
            if platform.lower() == "tiktok":
                # TikTok uses createTime (Unix timestamp), createTimeISO, or timestamp
                if "createTime" in item:
                    try:
                        post_date = datetime.fromtimestamp(item["createTime"]).date()
                    except:
                        pass
                elif "createTimeISO" in item:
                    try:
                        post_date = datetime.fromisoformat(str(item["createTimeISO"]).replace("Z", "+00:00")).date()
                    except:
                        pass
                elif "timestamp" in item:
                    try:
                        # Could be Unix timestamp or ISO string
                        if isinstance(item["timestamp"], (int, float)):
                            post_date = datetime.fromtimestamp(item["timestamp"]).date()
                        else:
                            post_date = datetime.fromisoformat(str(item["timestamp"]).replace("Z", "+00:00")).date()
                    except:
                        pass
            elif platform.lower() == "instagram":
                # Instagram uses timestamp in ISO format: "2024-02-13T20:49:57.000Z"
                if "timestamp" in item:
                    try:
                        timestamp_str = str(item["timestamp"])
                        # Handle ISO format with Z
                        if "Z" in timestamp_str or "+" in timestamp_str:
                            post_date = datetime.fromisoformat(timestamp_str.replace("Z", "+00:00")).date()
                        else:
                            post_date = datetime.fromisoformat(timestamp_str).date()
                    except Exception as e:
                        logger.debug(f"Could not parse Instagram timestamp: {item.get('timestamp')}, error: {e}")
                        pass
            elif platform.lower() == "facebook":
                # Facebook uses timestamp (Unix timestamp or ISO string) or createdAt (ISO string)
                if "timestamp" in item:
                    try:
                        timestamp_value = item["timestamp"]
                        if isinstance(timestamp_value, (int, float)):
                            # Unix timestamp
                            post_date = datetime.fromtimestamp(timestamp_value).date()
                        elif isinstance(timestamp_value, str):
                            # ISO format string
                            post_date = datetime.fromisoformat(timestamp_value.replace("Z", "+00:00")).date()
                    except Exception as e:
                        logger.debug(f"Could not parse Facebook timestamp: {item.get('timestamp')}, error: {e}")
                        pass
                elif "createdAt" in item:
                    try:
                        # Facebook createdAt is usually ISO format
                        post_date = datetime.fromisoformat(str(item["createdAt"]).replace("Z", "+00:00")).date()
                    except Exception as e:
                        logger.debug(f"Could not parse Facebook createdAt: {item.get('createdAt')}, error: {e}")
                        pass
            
            # If we couldn't extract date, include the post (better to include than exclude)
            if not post_date:
                logger.warning(f"Could not extract date from {platform} post, including it: {item.get('id', item.get('shortCode', 'unknown'))}")
                filtered_items.append(item)
                continue
            
            # Check if post is within date range
            if date_from and post_date < date_from:
                logger.debug(f"Excluding {platform} post from {post_date} (before {date_from})")
                continue
            if date_to and post_date > date_to:
                logger.debug(f"Excluding {platform} post from {post_date} (after {date_to})")
                continue
            
            filtered_items.append(item)
            logger.debug(f"Including {platform} post from {post_date}")
        
        logger.info(f"Date filter for {platform}: {len(items)} -> {len(filtered_items)} posts")
        return filtered_items
    
    def scrape_posts(
        self,
        platform: str,
        username: str,
        limit: Optional[int] = None,
        profile_id: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """
        Scrape posts for a given platform and username.
        Si profile_id está definido, usa la API key asociada a ese perfil (Facebook 1/2, Instagram, TikTok).
        Returns list of post dictionaries.
        """
        token = get_apify_token_for_profile(profile_id=profile_id) if profile_id else None
        if not token and not self._ensure_client():
            return []
        if token:
            self._ensure_client()  # asegurar que hay un token por defecto si el de perfil falla
        actor_id = get_actor_id(platform, "posts")
        if not actor_id:
            raise ValueError(f"No actor configured for {platform} posts")
        
        limit = limit or get_default_limit_posts()
        limit = max(1, min(500, int(limit)))  # Límite configurado (techo general)
        
        # Prioridad a fechas: si hay rango fecha inicio/fin, el actor debe devolver solo posts en ese rango.
        # No forzamos el límite (ej. 100); si en el rango hay 45, queremos 45, no 100.
        from config import get_last_days, get_date_from, get_date_to
        last_days = get_last_days()
        date_from_str = get_date_from()
        date_to_str = get_date_to()
        use_specific_dates = bool(date_from_str or date_to_str)
        has_date_filter = use_specific_dates or (last_days and last_days > 0)
        if has_date_filter:
            # Techo alto para que el actor devuelva todos los que caigan en el rango (el actor filtra por fecha)
            effective_limit = 500
            logger.info(f"Filtro de fechas activo: se piden hasta {effective_limit} posts en el rango de fechas (solo se usarán los que caigan en el rango; límite config={limit} es solo techo)")
        else:
            effective_limit = limit
        
        # Prepare input based on platform
        input_data = {}
        
        # Platform-specific input adjustments
        if platform.lower() == "instagram":
            # Instagram scraper expects directUrls (array of URL strings, not objects)
            # Based on actor logs showing "0 direct URL(s)" when using startUrls
            profile_url = f"https://www.instagram.com/{username}/"
            input_data = {
                "directUrls": [profile_url],  # Array of strings, not objects
                "resultsType": "posts",  # Scrape posts from profile
                "resultsLimit": effective_limit
            }
            
            # Apply date filter to actor if configured (fechas específicas tienen prioridad sobre últimos N días)
            if use_specific_dates and date_from_str:
                input_data["onlyPostsNewerThan"] = date_from_str
                logger.info(f"Instagram: Applying date filter to actor - onlyPostsNewerThan: {date_from_str}")
            elif last_days and last_days > 0:
                today = datetime.now().date()
                date_from = today - timedelta(days=last_days)
                input_data["onlyPostsNewerThan"] = date_from.strftime("%Y-%m-%d")
                logger.info(f"Instagram: Applying date filter to actor - onlyPostsNewerThan: {date_from} (last {last_days} days, excl. today)")
            
            logger.info(f"Instagram: Using directUrls format with profile URL: {profile_url}, limit: {effective_limit}")
        elif platform.lower() == "tiktok":
            # TikTok actor requires profiles array format
            # Enable comment scraping by setting commentsPerPost
            comments_limit = get_default_limit_comments()
            
            if has_date_filter:
                logger.info(f"TikTok: Date filter active - using limit {effective_limit} for date range (actor will filter by date)")
            else:
                logger.info(f"TikTok: No date filters - using limit {effective_limit}")
            
            # Actor: clockworks/tiktok-scraper (GdWCkxBtKWOsKjdch)
            # Formato exacto según la documentación del actor
            input_data = {
                "profiles": [f"@{username}"],  # El actor requiere @ antes del username
                "profileScrapeSections": ["videos"],
                "profileSorting": "latest",
                "resultsPerPage": effective_limit,
                "commentsPerPost": comments_limit,  # IMPORTANTE: Esto habilita el scraping de comentarios
                "maxRepliesPerComment": 10,
                "excludePinnedPosts": False,  # Incluir posts fijados
                "maxFollowersPerProfile": 0,
                "maxFollowingPerProfile": 0,
                "scrapeRelatedVideos": False,
                "shouldDownloadAvatars": False,
                "shouldDownloadCovers": False,
                "shouldDownloadMusicCovers": False,
                "shouldDownloadSlideshowImages": False,
                "shouldDownloadSubtitles": False,
                "shouldDownloadVideos": False,
                "proxyCountryCode": "None"
            }
            
            # Aplicar filtros de fecha al actor (fechas específicas tienen prioridad sobre últimos N días)
            if has_date_filter:
                today = datetime.now().date()
                if use_specific_dates:
                    if date_from_str:
                        input_data["oldestPostDateUnified"] = date_from_str
                    if date_to_str:
                        input_data["newestPostDate"] = date_to_str
                    logger.info(f"TikTok: Applying date filter to actor - from {date_from_str} to {date_to_str}")
                else:
                    actor_date_from = (today - timedelta(days=last_days)).strftime("%Y-%m-%d")
                    actor_date_to = (today - timedelta(days=1)).strftime("%Y-%m-%d")
                    input_data["oldestPostDateUnified"] = actor_date_from
                    input_data["newestPostDate"] = actor_date_to
                    logger.info(f"TikTok: Applying date filter to actor - from {actor_date_from} to {actor_date_to} (excl. today)")
            
            logger.info(f"TikTok: Using actor clockworks/tiktok-scraper with profile: @{username}, resultsPerPage: {effective_limit}, commentsPerPost: {comments_limit}")
        elif platform.lower() == "facebook":
            # Facebook actor requires startUrls array with resultsLimit
            # Soporta filtro de fechas: onlyPostsNewerThan (YYYY-MM-DD) y onlyPostsOlderThan (YYYY-MM-DD)
            profile_url = f"https://facebook.com/{username}"
            today = datetime.now().date()
            input_data = {
                "startUrls": [{"url": profile_url}],
                "resultsLimit": effective_limit
            }
            if has_date_filter:
                if use_specific_dates:
                    if date_from_str:
                        input_data["onlyPostsNewerThan"] = date_from_str
                    if date_to_str:
                        input_data["onlyPostsOlderThan"] = date_to_str
                    logger.info(f"Facebook: filtro de fechas en actor - desde {date_from_str or 'n/a'} hasta {date_to_str or 'n/a'}")
                else:
                    date_from = today - timedelta(days=last_days)
                    date_to = today - timedelta(days=1)
                    input_data["onlyPostsNewerThan"] = date_from.strftime("%Y-%m-%d")
                    input_data["onlyPostsOlderThan"] = date_to.strftime("%Y-%m-%d")
                    logger.info(f"Facebook: filtro de fechas en actor - desde {input_data['onlyPostsNewerThan']} hasta {input_data['onlyPostsOlderThan']} (excl. hoy)")
        else:
            input_data = {"usernames": [username], "resultsLimit": effective_limit}
        
        logger.info(f"Scraping up to {effective_limit} posts from {platform} user: {username}")
        logger.info(f"Using actor ID: {actor_id}")
        logger.info(f"Input data sent to actor: {input_data}")
        
        try:
            run = self._run_actor(actor_id, input_data, token=token)
            client = self._client_for_token(token)
            items = self._get_actor_dataset(run, client)
            count_total = len(items)
            logger.info(f"Retrieved {count_total} posts from actor")
            
            # Con filtro de fechas: devolver solo los que caen en el rango (ej. 45 en vez de 100)
            in_range = self._filter_posts_by_date(list(items), platform)
            if has_date_filter:
                count_in_range = len(in_range)
                logger.info(f"En rango de fechas: {count_in_range} de {count_total}. Se usan solo los {count_in_range} del rango.")
                return in_range
            return items
        except Exception as e:
            logger.error(f"Error scraping posts: {e}")
            raise
    
    def scrape_comments(
        self,
        platform: str,
        post_url: str,
        limit: Optional[int] = None,
        profile_id: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """
        Scrape comments for a given post URL.
        Si profile_id está definido, usa la API key del perfil.
        Returns list of comment dictionaries.
        """
        token = get_apify_token_for_profile(profile_id=profile_id) if profile_id else None
        if not token and not self._ensure_client():
            return []
        limit = limit or get_default_limit_comments()
        limit = max(1, min(1000, int(limit)))  # Respetar siempre el límite configurado (1-1000)
        
        # Prepare input based on platform
        input_data = {}
        
        # Platform-specific adjustments
        if platform.lower() == "instagram":
            # Use the same Instagram posts actor to scrape comments
            # The actor can scrape comments when given a post URL
            actor_id = get_actor_id(platform, "posts")  # Use posts actor, not comments actor
            if not actor_id:
                logger.warning(f"No actor configured for {platform} posts (needed for comments)")
                return []
            input_data = {
                "directUrls": [post_url],
                "resultsType": "comments",  # Scrape comments from post
                "resultsLimit": limit
            }
        elif platform.lower() == "tiktok":
            actor_id = get_actor_id(platform, "comments")
            if not actor_id:
                logger.warning(f"No actor configured for {platform} comments")
                return []
            input_data = {"urls": [post_url], "maxComments": limit}
        elif platform.lower() == "facebook":
            actor_id = get_actor_id(platform, "comments")
            if not actor_id:
                logger.warning(f"No actor configured for {platform} comments")
                return []
            # Facebook comments scraper uses startUrls format
            input_data = {
                "startUrls": [{"url": post_url}],
                "resultsLimit": limit,
                "includeNestedComments": False,  # Set to True if you want nested comments
                "viewOption": "RANKED_UNFILTERED"
            }
        else:
            actor_id = get_actor_id(platform, "comments")
            if not actor_id:
                logger.warning(f"No actor configured for {platform} comments")
                return []
            input_data = {"postUrls": [post_url], "maxComments": limit}
        
        logger.info(f"Scraping comments from {platform} post (limit={limit}): {post_url[:80]}...")
        logger.info(f"Using actor ID: {actor_id}, resultsLimit={limit}")
        
        try:
            run = self._run_actor(actor_id, input_data, token=token)
            client = self._client_for_token(token)
            items = self._get_actor_dataset(run, client)
            logger.info(f"Retrieved {len(items)} comments")
            return items
        except Exception as e:
            logger.warning(f"Error scraping comments (non-critical): {e}")
            return []  # Comments are optional, don't fail the whole process
    
    def process_post_item(
        self,
        item: Dict[str, Any],
        platform: str,
        profile_id: int
    ) -> Optional[int]:
        """
        Process a single post item and insert into database.
        Returns the post database ID.
        """
        try:
            # Extract post data (structure varies by platform)
            # TikTok uses different field names
            if platform.lower() == "tiktok":
                post_id = (
                    item.get("id") or 
                    item.get("awemeId") or  # TikTok specific
                    item.get("videoId") or  # TikTok specific
                    str(item.get("videoWebUrl", "")) or
                    str(item.get("url", ""))
                )
                url = item.get("videoWebUrl") or item.get("webVideoUrl") or item.get("url")
                text = clean_text(item.get("text") or item.get("desc") or item.get("description"))
                
                # TikTok engagement metrics
                likes = int(item.get("diggCount") or item.get("likesCount") or item.get("likes") or 0)
                comments_count = int(item.get("commentCount") or item.get("commentsCount") or item.get("comments") or 0)
                shares = int(item.get("shareCount") or item.get("sharesCount") or item.get("shares") or 0)
                views = int(item.get("playCount") or item.get("viewsCount") or item.get("views") or item.get("viewCount") or 0)
                
                # TikTok timestamp parsing
                posted_at = None
                if "createTime" in item:
                    try:
                        # TikTok uses Unix timestamp in createTime
                        posted_at = datetime.fromtimestamp(item["createTime"])
                    except:
                        pass
                elif "createTimeISO" in item:
                    try:
                        posted_at = datetime.fromisoformat(str(item["createTimeISO"]).replace("Z", "+00:00"))
                    except:
                        pass
                elif "timestamp" in item:
                    try:
                        posted_at = datetime.fromtimestamp(item["timestamp"])
                    except:
                        pass
            else:
                # Instagram, Facebook, etc.
                post_id = item.get("id") or item.get("postId") or item.get("shortCode") or str(item.get("url", ""))
                url = item.get("url") or item.get("postUrl") or item.get("webVideoUrl")
                text = clean_text(item.get("text") or item.get("caption") or item.get("description"))
                
                # Extract engagement metrics
                likes = int(item.get("likesCount") or item.get("likes") or item.get("diggCount") or item.get("reactionsCount") or 0)
                comments_count = int(item.get("commentsCount") or item.get("comments") or item.get("commentCount") or 0)
                shares = int(item.get("sharesCount") or item.get("shares") or item.get("shareCount") or 0)
                views = int(item.get("viewsCount") or item.get("views") or item.get("playCount") or item.get("viewCount") or 0)
                
                # Parse posted_at timestamp
                posted_at = None
                if "timestamp" in item:
                    try:
                        timestamp_value = item["timestamp"]
                        # Instagram uses ISO format strings, TikTok/Facebook may use Unix timestamps
                        if isinstance(timestamp_value, str):
                            # ISO format string (Instagram)
                            posted_at = datetime.fromisoformat(timestamp_value.replace("Z", "+00:00"))
                        elif isinstance(timestamp_value, (int, float)):
                            # Unix timestamp (TikTok/Facebook)
                            posted_at = datetime.fromtimestamp(timestamp_value)
                    except Exception as e:
                        logger.debug(f"Could not parse timestamp: {e}")
                        pass
                elif "createdAt" in item:
                    try:
                        posted_at = datetime.fromisoformat(str(item["createdAt"]).replace("Z", "+00:00"))
                    except:
                        pass
            
            # Extract comments if they're embedded in the post data (for all platforms)
            embedded_comments = item.get("comments") or item.get("commentsData") or item.get("topComments") or []
            
            post_db_id = insert_post(
                profile_id=profile_id,
                platform=platform,
                post_id=post_id,
                url=url,
                text=text,
                likes=likes,
                comments_count=comments_count,
                shares=shares,
                views=views,
                posted_at=posted_at
            )
            
            # Store embedded comments for later processing (if any)
            if embedded_comments and isinstance(embedded_comments, list):
                item["_embedded_comments"] = embedded_comments
            
            logger.debug(f"Processed {platform} post: {post_id[:50]}... (likes: {likes}, comments: {comments_count})")
            return post_db_id
        except Exception as e:
            logger.error(f"Error processing {platform} post item: {e}")
            logger.error(f"Item keys: {list(item.keys()) if isinstance(item, dict) else 'not a dict'}")
            return None
    
    def process_comment_item(
        self,
        item: Dict[str, Any],
        post_db_id: int
    ) -> None:
        """Process a single comment item and insert into database with sentiment."""
        try:
            # Extract text first (needed for fallback comment_id)
            text = clean_text(
                item.get("text") or 
                item.get("comment") or 
                item.get("content")
            )
            author = (
                item.get("ownerUsername") or
                item.get("author") or
                item.get("username") or
                item.get("uniqueId") or  # TikTok uses "uniqueId"
                item.get("authorMeta", {}).get("name")  # TikTok nested format
            )
            # TikTok: siempre usar hash(post + texto + autor) como comment_id para evitar duplicados
            # (el actor a veces devuelve el mismo comentario varias veces con ids distintos en la misma publicación)
            post_info = get_post_profile_and_platform(post_db_id)
            is_tiktok = post_info and post_info[1] == "tiktok"
            if is_tiktok:
                payload = f"{post_db_id}_{text or ''}_{author or ''}"
                comment_id = hashlib.sha256(payload.encode("utf-8")).hexdigest()[:32]
            else:
                raw_id = item.get("id") or item.get("commentId") or item.get("cid")
                if raw_id is not None and str(raw_id).strip():
                    comment_id = str(raw_id).strip()
                else:
                    payload = f"{post_db_id}_{text or ''}_{author or ''}"
                    comment_id = hashlib.sha256(payload.encode("utf-8")).hexdigest()[:32]
            
            # Extract likes (field names vary by platform)
            likes = int(
                item.get("likesCount") or 
                item.get("likes") or 
                item.get("diggCount") or  # TikTok uses "diggCount"
                0
            )
            
            # Parse posted_at timestamp (multiple formats)
            posted_at = None
            if "timestamp" in item:
                try:
                    posted_at = datetime.fromtimestamp(item["timestamp"])
                except:
                    pass
            elif "createTime" in item:
                try:
                    # TikTok uses createTime as Unix timestamp
                    posted_at = datetime.fromtimestamp(item["createTime"])
                except:
                    pass
            elif "createTimeISO" in item:
                try:
                    posted_at = datetime.fromisoformat(str(item["createTimeISO"]).replace("Z", "+00:00"))
                except:
                    pass
            elif "createdAt" in item:
                try:
                    posted_at = datetime.fromisoformat(str(item["createdAt"]).replace("Z", "+00:00"))
                except:
                    pass
            
            # Analyze sentiment
            analyzer = get_analyzer()
            sentiment_result = analyzer.analyze(text) if text else {
                "label": "NEUTRAL",
                "score": 0.5,
                "method": "empty"
            }
            
            insert_comment(
                post_id=post_db_id,
                comment_id=comment_id,
                text=text,
                author=author,
                likes=likes,
                sentiment_label=sentiment_result["label"],
                sentiment_score=sentiment_result["score"],
                sentiment_method=sentiment_result["method"],
                posted_at=posted_at
            )
        except Exception as e:
            logger.error(f"Error processing comment item: {e}")
    
    def analyze_profile(
        self,
        profile_id: int,
        platform: str,
        username: str,
        force: bool = False
    ) -> Dict[str, Any]:
        """
        Analyze a complete profile: scrape posts and comments.
        Returns summary statistics.
        """
        # Check if should skip (analyzed recently)
        # BUT: Skip auto-skip if date filters are configured (respect date filters strictly)
        # Date filters apply to ALL platforms now
        from config import get_last_days, get_date_from, get_date_to
        last_days = get_last_days()
        date_from = get_date_from()
        date_to = get_date_to()
        has_date_filters = (last_days and last_days > 0) or date_from or date_to
        
        if not force and get_auto_skip_recent() and not has_date_filters:
            # Only apply auto-skip if no date filters are configured
            from db_utils import get_connection
            conn = get_connection()
            cursor = conn.cursor()
            cursor.execute(
                "SELECT last_analyzed FROM profiles WHERE id = ?",
                (profile_id,)
            )
            row = cursor.fetchone()
            conn.close()
            
            if row and row[0]:
                try:
                    last_analyzed = datetime.fromisoformat(row[0])
                    days_since = (datetime.now() - last_analyzed).days
                    if days_since < 7:
                        logger.info(f"Skipping {username} (analyzed {last_analyzed}, {days_since} days ago)")
                        return {"skipped": True, "reason": "analyzed_recently"}
                    else:
                        logger.info(f"Will analyze {username} (last analyzed {days_since} days ago, > 7 days)")
                except:
                    pass
        elif has_date_filters:
            logger.info(f"Date filters configured for {platform}, ignoring auto-skip and analyzing according to date filters")
        
        logger.info(f"Starting analysis for {platform} profile: {username}")
        # Log límites en uso (para verificar que se respeta la config)
        limit_posts_cfg = get_default_limit_posts()
        limit_comments_cfg = get_default_limit_comments()
        logger.info(f"Límites en uso: max posts={limit_posts_cfg}, max comentarios por post={limit_comments_cfg}")
        
        stats = {
            "posts_scraped": 0,
            "comments_scraped": 0,
            "errors": []
        }
        
        try:
            # Scrape posts (usa la API key del perfil si está configurada)
            posts = self.scrape_posts(platform, username, profile_id=profile_id)
            stats["posts_scraped"] = len(posts)
            logger.info(f"Retrieved {len(posts)} posts from {platform}, processing...")
            
            # TikTok: el actor a veces devuelve la MISMA URL de dataset para todos los posts (dataset global del run).
            # Si usamos esa URL por cada post, asignamos los mismos comentarios a todos los videos (duplicados masivos).
            # Solo usamos cada commentsDatasetUrl una vez; si hay que filtrar por video, se hace más abajo.
            tiktok_dataset_url_used = set()
            tiktok_dataset_cache = {}  # url -> list of comment items (para filtrar por video si aplica)
            
            # Process each post
            posts_processed = 0
            for idx, post_item in enumerate(posts):
                logger.debug(f"Processing {platform} post {idx+1}/{len(posts)}")
                post_db_id = self.process_post_item(post_item, platform, profile_id)
                if post_db_id:
                    posts_processed += 1
                else:
                    logger.warning(f"Failed to process {platform} post {idx+1}: {list(post_item.keys())[:5] if isinstance(post_item, dict) else 'not a dict'}")
                
                if post_db_id:
                    # Try to get comments from post item first (some actors include comments in post data)
                    # Note: "comments" field might be an integer (count) or a list (actual comments)
                    comments_from_post = None
                    comments_list = []
                    
                    # Log post item keys for debugging
                    logger.debug(f"TikTok post item keys: {list(post_item.keys())[:10]}")
                    
                    # Check for embedded comments in various fields
                    for field in ["_embedded_comments", "commentsData", "topComments", "commentsList"]:
                        if field in post_item:
                            if isinstance(post_item[field], list):
                                comments_list = post_item[field]
                                comments_from_post = comments_list
                                logger.info(f"Found {len(comments_list)} comments in field '{field}'")
                                break
                            else:
                                logger.debug(f"Field '{field}' exists but is not a list: {type(post_item[field])}")
                    
                    # Also check "comments" field, but be careful - it might be a count
                    if not comments_list and "comments" in post_item:
                        if isinstance(post_item["comments"], list):
                            comments_list = post_item["comments"]
                            comments_from_post = comments_list
                            logger.info(f"Found {len(comments_list)} comments in 'comments' field")
                        else:
                            logger.debug(f"'comments' field is not a list (type: {type(post_item['comments'])}, value: {post_item['comments']})")
                    
                    if comments_list and len(comments_list) > 0:
                        # Process comments that came with the post
                        logger.info(f"Processing {len(comments_list)} embedded comments from post data")
                        for comment_item in comments_list:
                            self.process_comment_item(comment_item, post_db_id)
                        stats["comments_scraped"] += len(comments_list)
                    
                    # For TikTok: Check if comments are in a separate dataset URL.
                    # IMPORTANTE: El actor suele devolver la MISMA URL para todos los posts (dataset global del run).
                    # Si la usáramos en cada post, asignaríamos los mismos comentarios a todos los videos (duplicados).
                    # Solución: cachear por URL, filtrar comentarios por video (awemeId/videoId) y solo procesar los de este post.
                    if platform.lower() == "tiktok" and not comments_list:
                        comments_dataset_url = post_item.get("commentsDatasetUrl") or post_item.get("commentsDatasetURL") or post_item.get("commentsUrl")
                        if comments_dataset_url:
                            try:
                                # Obtener id del video de este post (para filtrar comentarios)
                                post_video_id = str(
                                    post_item.get("id") or
                                    post_item.get("awemeId") or
                                    post_item.get("videoId") or
                                    ""
                                ).strip()
                                # Usar cache: la misma URL devuelve todos los comentarios del run
                                if comments_dataset_url not in tiktok_dataset_cache:
                                    logger.info(f"Fetching TikTok comments from dataset URL (once per run)")
                                    response = requests.get(comments_dataset_url, timeout=30)
                                    if response.status_code == 200:
                                        all_comments = response.json()
                                        tiktok_dataset_cache[comments_dataset_url] = all_comments if isinstance(all_comments, list) else []
                                    else:
                                        logger.warning(f"Failed to fetch TikTok comments: HTTP {response.status_code}")
                                        tiktok_dataset_cache[comments_dataset_url] = []
                                all_from_url = tiktok_dataset_cache.get(comments_dataset_url) or []
                                # Filtrar: solo comentarios de este video (el dataset puede mezclar todos los videos)
                                tiktok_comments = []
                                for c in all_from_url:
                                    if not isinstance(c, dict):
                                        continue
                                    c_video_id = str(
                                        c.get("awemeId") or c.get("videoId") or c.get("postId") or ""
                                    ).strip()
                                    if not c_video_id:
                                        c_url = (c.get("url") or c.get("videoUrl") or c.get("webVideoUrl") or "")
                                        if post_video_id and post_video_id in str(c_url):
                                            c_video_id = post_video_id
                                    if c_video_id and post_video_id and c_video_id == post_video_id:
                                        tiktok_comments.append(c)
                                    elif not post_video_id:
                                        tiktok_comments.append(c)
                                if tiktok_comments:
                                    logger.info(f"Retrieved {len(tiktok_comments)} comments for this video (from dataset, filtered by video id)")
                                    for comment_item in tiktok_comments:
                                        self.process_comment_item(comment_item, post_db_id)
                                    stats["comments_scraped"] += len(tiktok_comments)
                                    comments_list = tiktok_comments
                                    tiktok_dataset_url_used.add(comments_dataset_url)
                                elif all_from_url and not post_video_id and comments_dataset_url not in tiktok_dataset_url_used:
                                    logger.info(f"Retrieved {len(all_from_url)} comments from TikTok dataset (no video id in post to filter; using only for this post to avoid duplicates)")
                                    for comment_item in all_from_url:
                                        if isinstance(comment_item, dict):
                                            self.process_comment_item(comment_item, post_db_id)
                                    stats["comments_scraped"] += len([c for c in all_from_url if isinstance(c, dict)])
                                    comments_list = all_from_url
                                    tiktok_dataset_url_used.add(comments_dataset_url)
                                elif all_from_url and comments_dataset_url not in tiktok_dataset_url_used:
                                    # Fallback: el dataset no trae awemeId/videoId en comentarios, no podemos filtrar por video.
                                    # Asignamos todos al primer post que ve esta URL para no perder comentarios ni duplicar en todos.
                                    logger.info(f"Retrieved {len(all_from_url)} comments from TikTok dataset (no video id in comments; assigning to first post only to avoid duplicates)")
                                    for comment_item in all_from_url:
                                        if isinstance(comment_item, dict):
                                            self.process_comment_item(comment_item, post_db_id)
                                    stats["comments_scraped"] += len([c for c in all_from_url if isinstance(c, dict)])
                                    comments_list = all_from_url
                                    tiktok_dataset_url_used.add(comments_dataset_url)
                                else:
                                    if all_from_url and post_video_id and comments_dataset_url not in tiktok_dataset_url_used:
                                        logger.debug(f"Dataset has {len(all_from_url)} comments but none match video id {post_video_id}; will use fallback on first post")
                                    elif comments_dataset_url in tiktok_dataset_url_used:
                                        logger.debug(f"Same dataset URL already used for another post; skipping to avoid duplicate comments")
                            except Exception as e:
                                logger.warning(f"Error fetching TikTok comments from dataset: {e}")
                        else:
                            logger.debug(f"No commentsDatasetUrl found in post item. Available keys: {list(post_item.keys())[:15]}")
                    
                    # Pedir comentarios por URL solo cuando no vienen embebidos (o en Facebook).
                    # En Facebook cada post = 1 run Apify; limitar a los primeros 20 posts para ahorrar cuota.
                    num_comments_found = len(comments_list) if comments_list else 0
                    post_url = post_item.get("url") or post_item.get("postUrl") or post_item.get("link")
                    should_fetch = (num_comments_found < 5) or (platform.lower() == "facebook")
                    if platform.lower() == "facebook" and idx >= 20:
                        should_fetch = False
                        logger.debug(f"Facebook: omitiendo comentarios por URL para post {idx+1} (solo primeros 20)")
                    if post_url and should_fetch:
                        try:
                            comments = self.scrape_comments(platform, post_url, profile_id=profile_id)
                            if comments and len(comments) > 0:
                                logger.info(f"Scraped {len(comments)} additional comments from URL")
                                stats["comments_scraped"] += len(comments)
                                # Process each comment
                                for comment_item in comments:
                                    self.process_comment_item(comment_item, post_db_id)
                        except Exception as e:
                            error_msg = str(e)
                            # Only log as warning if it's not a critical error
                            if "not found" not in error_msg.lower() and "actor" not in error_msg.lower():
                                logger.warning(f"Error scraping comments: {error_msg}")
                                stats["errors"].append(error_msg)
                            else:
                                logger.debug(f"Comments actor not available or not found: {error_msg}")
            
            # Update last_analyzed timestamp
            update_profile_last_analyzed(profile_id)
            
            logger.info(f"Analysis complete for {platform} profile {username}: {stats}")
            logger.info(f"Posts processed successfully: {posts_processed}/{stats['posts_scraped']}")
            return stats
            
        except Exception as e:
            error_msg = f"Error analyzing profile {username}: {e}"
            logger.error(error_msg)
            stats["errors"].append(error_msg)
            return stats


def analyze_profiles(profile_ids: Optional[List[int]] = None, force: bool = False) -> Dict[str, Any]:
    """
    Analyze multiple profiles.
    If profile_ids is None, analyzes all profiles.
    """
    scraper = ApifyScraper()
    profiles = get_all_profiles()
    
    if profile_ids:
        profiles = [p for p in profiles if p["id"] in profile_ids]
    
    results = {}
    
    for profile in profiles:
        try:
            result = scraper.analyze_profile(
                profile_id=profile["id"],
                platform=profile["platform"],
                username=profile["username_or_url"],
                force=force
            )
            results[profile["id"]] = result
        except Exception as e:
            results[profile["id"]] = {"error": str(e)}
    
    return results
