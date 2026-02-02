"""
Web scraping module using Apify actors.
Handles scraping posts and comments from Instagram, TikTok, and Facebook.
"""
import logging
from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta
import requests
from apify_client import ApifyClient
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

from config import (
    get_apify_token, get_actor_id, get_default_limit_posts,
    get_default_limit_comments, get_auto_skip_recent,
    get_date_from, get_date_to, get_last_days
)
from db_utils import (
    get_all_profiles, update_profile_last_analyzed, insert_post, insert_comment
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
    
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        retry=retry_if_exception_type((ConnectionError, TimeoutError))
    )
    def _run_actor(self, actor_id: str, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """Run an Apify actor with retry logic."""
        self._ensure_client()
        
        try:
            run = self.client.actor(actor_id).call(run_input=input_data)
            return run
        except Exception as e:
            logger.error(f"Error running actor {actor_id}: {e}")
            if "unauthorized" in str(e).lower() or "token" in str(e).lower():
                raise ValueError(f"Invalid Apify token: {e}")
            raise
    
    def _get_actor_dataset(self, run: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Get dataset items from an Apify actor run."""
        if not run or "defaultDatasetId" not in run:
            return []
        
        dataset_id = run["defaultDatasetId"]
        items = []
        
        try:
            for item in self.client.dataset(dataset_id).iterate_items():
                items.append(item)
        except Exception as e:
            logger.error(f"Error fetching dataset items: {e}")
        
        return items
    
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
        
        # Calculate date range
        today = datetime.now().date()
        date_from = None
        date_to = None
        
        # If last_days is set, calculate date_from (takes priority)
        if last_days and last_days > 0:
            date_from = today - timedelta(days=last_days - 1)  # Inclusive: includes today
            date_to = today
            logger.info(f"Filtering {platform} posts: last {last_days} days (from {date_from} to {date_to})")
        else:
            # Use specific date range if provided
            if date_from_str:
                try:
                    date_from = datetime.strptime(date_from_str, "%Y-%m-%d").date()
                except:
                    pass
            if date_to_str:
                try:
                    date_to = datetime.strptime(date_to_str, "%Y-%m-%d").date()
                except:
                    pass
            if date_from or date_to:
                logger.info(f"Filtering {platform} posts: from {date_from} to {date_to}")
        
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
        limit: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """
        Scrape posts for a given platform and username.
        Returns list of post dictionaries.
        """
        if not self._ensure_client():
            return []
        
        actor_id = get_actor_id(platform, "posts")
        if not actor_id:
            raise ValueError(f"No actor configured for {platform} posts")
        
        limit = limit or get_default_limit_posts()
        
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
                "resultsLimit": limit
            }
            
            # Apply date filter to actor if configured (saves tokens)
            from config import get_last_days, get_date_from, get_date_to
            last_days = get_last_days()
            date_from_str = get_date_from()
            date_to_str = get_date_to()
            
            # Calculate onlyPostsNewerThan date (Instagram actor supports this parameter)
            if last_days and last_days > 0:
                # Calculate date from (last N days)
                today = datetime.now().date()
                date_from = today - timedelta(days=last_days - 1)  # Inclusive: includes today
                input_data["onlyPostsNewerThan"] = date_from.strftime("%Y-%m-%d")
                logger.info(f"Instagram: Applying date filter to actor - onlyPostsNewerThan: {input_data['onlyPostsNewerThan']} (last {last_days} days)")
            elif date_from_str:
                # Use specific date_from if provided
                input_data["onlyPostsNewerThan"] = date_from_str
                logger.info(f"Instagram: Applying date filter to actor - onlyPostsNewerThan: {date_from_str}")
            
            logger.info(f"Instagram: Using directUrls format with profile URL: {profile_url}, limit: {limit}")
        elif platform.lower() == "tiktok":
            # TikTok actor requires profiles array format
            # Enable comment scraping by setting commentsPerPost
            comments_limit = get_default_limit_comments()
            
            # Check if date filters are active
            from config import get_last_days, get_date_from, get_date_to
            last_days = get_last_days()
            date_from_str = get_date_from()
            date_to_str = get_date_to()
            
            has_date_filter = (last_days and last_days > 0) or date_from_str or date_to_str
            
            # Usar el límite configurado directamente
            # El actor aplica filtros de fecha, así que no necesitamos multiplicar
            # El filtrado manual adicional asegura que solo obtenemos videos en el rango correcto
            effective_limit = limit
            if has_date_filter:
                logger.info(f"TikTok: Date filter active - using limit {limit} (actor will filter by date)")
            else:
                logger.info(f"TikTok: No date filters - using limit {limit}")
            
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
            
            # Aplicar filtros de fecha al actor para evitar obtener videos muy antiguos
            if has_date_filter:
                today = datetime.now().date()
                
                if last_days and last_days > 0:
                    # Calcular fecha desde (últimos N días)
                    actor_date_from = (today - timedelta(days=last_days - 1)).strftime("%Y-%m-%d")
                    actor_date_to = today.strftime("%Y-%m-%d")
                    input_data["oldestPostDateUnified"] = actor_date_from
                    input_data["newestPostDate"] = actor_date_to
                    logger.info(f"TikTok: Applying date filter to actor - from {actor_date_from} to {actor_date_to}")
                elif date_from_str or date_to_str:
                    if date_from_str:
                        input_data["oldestPostDateUnified"] = date_from_str
                    if date_to_str:
                        input_data["newestPostDate"] = date_to_str
                    logger.info(f"TikTok: Applying date filter to actor - from {date_from_str} to {date_to_str}")
            
            logger.info(f"TikTok: Using actor clockworks/tiktok-scraper with profile: @{username}")
            logger.info(f"TikTok input - resultsPerPage: {effective_limit}, commentsPerPost: {comments_limit}")
            
            logger.info(f"TikTok input - resultsLimit: {limit}, commentsPerPost: {comments_limit}")
        elif platform.lower() == "facebook":
            # Facebook actor requires startUrls array with resultsLimit
            profile_url = f"https://facebook.com/{username}"
            input_data = {
                "startUrls": [{"url": profile_url}],
                "resultsLimit": limit  # Use resultsLimit instead of deprecated maxPosts
            }
        else:
            input_data = {"usernames": [username], "resultsLimit": limit}
        
        logger.info(f"Scraping {limit} posts from {platform} user: {username}")
        logger.info(f"Using actor ID: {actor_id}")
        logger.info(f"Input data sent to actor: {input_data}")
        
        try:
            run = self._run_actor(actor_id, input_data)
            items = self._get_actor_dataset(run)
            logger.info(f"Retrieved {len(items)} posts from actor")
            
            # Filter by date manually for ALL platforms
            # (TikTok actor's date filter is too aggressive, Instagram doesn't support date filters in actor, Facebook needs manual filtering)
            items = self._filter_posts_by_date(items, platform)
            logger.info(f"After date filtering: {len(items)} posts")
            
            return items
        except Exception as e:
            logger.error(f"Error scraping posts: {e}")
            raise
    
    def scrape_comments(
        self,
        platform: str,
        post_url: str,
        limit: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """
        Scrape comments for a given post URL.
        Returns list of comment dictionaries.
        """
        if not self._ensure_client():
            return []
        
        limit = limit or get_default_limit_comments()
        
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
        
        logger.info(f"Scraping comments from {platform} post: {post_url}")
        logger.info(f"Using actor ID: {actor_id}")
        logger.info(f"Input data sent to actor: {input_data}")
        
        try:
            run = self._run_actor(actor_id, input_data)
            items = self._get_actor_dataset(run)
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
            # Extract comment ID (format varies by platform)
            comment_id = (
                item.get("id") or 
                item.get("commentId") or 
                item.get("cid") or  # TikTok uses "cid"
                str(item.get("text", ""))[:50]
            )
            
            # Extract text (field names vary by platform)
            text = clean_text(
                item.get("text") or 
                item.get("comment") or 
                item.get("content")
            )
            
            # Extract author (field names vary by platform)
            author = (
                item.get("ownerUsername") or 
                item.get("author") or 
                item.get("username") or
                item.get("uniqueId") or  # TikTok uses "uniqueId"
                item.get("authorMeta", {}).get("name")  # TikTok nested format
            )
            
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
        
        stats = {
            "posts_scraped": 0,
            "comments_scraped": 0,
            "errors": []
        }
        
        try:
            # Scrape posts
            posts = self.scrape_posts(platform, username)
            stats["posts_scraped"] = len(posts)
            logger.info(f"Retrieved {len(posts)} posts from {platform}, processing...")
            
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
                    
                    # For TikTok: Check if comments are in a separate dataset URL
                    if platform.lower() == "tiktok" and not comments_list:
                        comments_dataset_url = post_item.get("commentsDatasetUrl") or post_item.get("commentsDatasetURL") or post_item.get("commentsUrl")
                        if comments_dataset_url:
                            try:
                                logger.info(f"Fetching TikTok comments from dataset URL: {comments_dataset_url}")
                                # Fetch comments from the dataset URL
                                response = requests.get(comments_dataset_url, timeout=30)
                                if response.status_code == 200:
                                    tiktok_comments = response.json()
                                    if isinstance(tiktok_comments, list) and len(tiktok_comments) > 0:
                                        logger.info(f"Retrieved {len(tiktok_comments)} comments from TikTok dataset")
                                        for comment_item in tiktok_comments:
                                            self.process_comment_item(comment_item, post_db_id)
                                        stats["comments_scraped"] += len(tiktok_comments)
                                        comments_list = tiktok_comments  # Mark as found
                                    else:
                                        logger.warning(f"TikTok comments dataset returned non-list or empty: {type(tiktok_comments)}")
                                else:
                                    logger.warning(f"Failed to fetch TikTok comments: HTTP {response.status_code}")
                            except Exception as e:
                                logger.warning(f"Error fetching TikTok comments from dataset: {e}")
                        else:
                            logger.debug(f"No commentsDatasetUrl found in post item. Available keys: {list(post_item.keys())[:15]}")
                    
                    # Also try to scrape comments separately if post has URL and we haven't got many comments
                    num_comments_found = len(comments_list) if comments_list else 0
                    if post_item.get("url") and num_comments_found < 5:
                        try:
                            comments = self.scrape_comments(platform, post_item["url"])
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
