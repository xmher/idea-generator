# main_romantasy.py
# VERSION 1.0: Romantasy Writing Advice Blog - Idea Generator
# Integrated RSS feeds + Reddit auto-discovery with shared relevance filtering

import os, re, json, argparse, logging, time, hashlib
from typing import Any, Dict, List, Optional
from urllib.parse import urlparse
from datetime import datetime, timezone, timedelta

import requests
from requests.auth import HTTPBasicAuth
from bs4 import BeautifulSoup
import anthropic

try:
    from openai import OpenAI
except ImportError:
    print("FATAL: Missing 'openai' library. Install with 'pip install openai'.")
    raise SystemExit(1)

try:
    import praw
except ImportError:
    praw = None
    print("WARNING: Missing 'praw' library. Reddit API unavailable.")

try:
    import feedparser
except ImportError:
    feedparser = None
    print("WARNING: Missing 'feedparser' library. RSS feeds unavailable. Install with 'pip install feedparser'.")

import prompts_romantasy as P

# ---------- Logging ----------
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()
logging.basicConfig(
    level=getattr(logging, LOG_LEVEL, logging.INFO),
    format="%(asctime)s | %(levelname)s | %(message)s"
)
log = logging.getLogger("pipeline-seo")

try:
    from dotenv import load_dotenv
    load_dotenv()
except Exception:
    pass

# --- API Keys & Clients ---
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")

if not OPENAI_API_KEY:
    raise SystemExit("OPENAI_API_KEY not set")
if not ANTHROPIC_API_KEY:
    raise SystemExit("ANTHROPIC_API_KEY not set")

client = OpenAI(api_key=OPENAI_API_KEY, timeout=180.0)
anthropic_client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY, timeout=180.0)

# Reddit API
REDDIT_CLIENT_ID = os.getenv("REDDIT_CLIENT_ID")
REDDIT_CLIENT_SECRET = os.getenv("REDDIT_CLIENT_SECRET")
REDDIT_USER_AGENT = os.getenv("REDDIT_USER_AGENT", "python:blog-pipeline:v1.0")

reddit_client = None
if praw and REDDIT_CLIENT_ID and REDDIT_CLIENT_SECRET:
    try:
        reddit_client = praw.Reddit(
            client_id=REDDIT_CLIENT_ID,
            client_secret=REDDIT_CLIENT_SECRET,
            user_agent=REDDIT_USER_AGENT,
        )
        log.info("Reddit API initialized")
    except Exception as e:
        log.error(f"Reddit API init failed: {e}")

# --- Model routing ---
MODEL_MAP = {
    "relevance_filter": "gpt-5-nano",
    "angle_and_plan": "claude-sonnet-4-5",
    # Keyphrase model removed
}
API_MAX_RETRIES = 3

# --- Discovery Time Window (Shared by Reddit & RSS) ---
DISCOVERY_HOURS_WINDOW = 168  # 7 days - run weekly or a few times per week

# --- Reddit Auto-Discovery Configuration ---
SUBREDDIT_CONFIG = {
    # --- Pillar 1: Romantasy Craft & Structure ---
    "RomanceBooks": 50,           # Romance readers discussing tropes and books
    "romantasy": 25,              # Romantasy-specific community
    "fantasyromance": 25,         # Fantasy romance community
    "Fantasy": 75,                # Fantasy craft and worldbuilding
    "fantasywriters": 25,         # Fantasy writing craft
    "RomanceAuthors": 10,         # Romance author community

    # --- Pillar 2: Market Trends & Publishing ---
    "YAwriters": 50,              # YA (includes romantasy) writing community
    "selfpublish": 50,            # Self-publishing trends and strategies
    "PubTips": 25,                # Traditional publishing queries/deals
    "BookTok": 50,                # BookTok trends

    # --- Pillar 3: Reader Psychology & Audience ---
    "romancelandia": 25,          # Romance reader community
    "suggestmeabook": 75,         # What readers are asking for
    "booksuggestions": 75,        # Reader preferences
    "YAlit": 50,                  # YA reader community

    # --- Cross-Pillar: Writing & Genre ---
    "writing": 100,               # General writing community
    "writers": 100,               # Writer discussions
}

MIN_PROCESSING_SCORE = 0.65  # Lowered from 0.70 to catch more good Reddit posts
PROCESSED_IDS_FILE = "processed_posts_romantasy.txt"

# --- RSS Feed Sources Configuration ---
RSS_FEEDS = [
    # Pillar 1: Romantasy Craft & Structure
    {"name": "Jane Friedman", "url": "https://www.janefriedman.com/feed/", "priority": "high"},
    {"name": "Writer's Digest", "url": "https://www.writersdigest.com/feed", "priority": "high"},
    {"name": "DIY MFA", "url": "https://diymfa.com/feed", "priority": "medium"},

    # Pillar 2: Market Trends & Publishing
    {"name": "Publishers Weekly", "url": "https://www.publishersweekly.com/pw/feeds/recent/index.xml", "priority": "high"},
    {"name": "The Passive Voice", "url": "https://www.thepassivevoice.com/feed/", "priority": "high"},
    {"name": "Publishers Marketplace", "url": "https://lunch.publishersmarketplace.com/feed/", "priority": "medium"},
    {"name": "Kirkus Reviews", "url": "https://www.kirkusreviews.com/feeds/reviews/", "priority": "medium"},

    # Pillar 3: Reader Psychology & Genre Trends
    {"name": "BookRiot", "url": "https://bookriot.com/feed/", "priority": "high"},
    {"name": "Smart Bitches Trashy Books", "url": "https://smartbitchestrashybooks.com/feed/", "priority": "high"},
    {"name": "Dear Author", "url": "https://dearauthor.com/feed/", "priority": "medium"},

    # Writing Craft & Industry (Cross-Pillar)
    {"name": "Chuck Wendig", "url": "https://terribleminds.com/ramble/feed/", "priority": "medium"},
    {"name": "Helping Writers Become Authors", "url": "https://www.helpingwritersbecomeauthors.com/feed/", "priority": "medium"},
]

RSS_CONFIG = {
    "max_entries_per_feed": 20,
    "use_high_priority_only": True,
}

# -------- RSS Fetching Functions --------
def fetch_rss_candidates() -> List[Dict[str, Any]]:
    """Fetch and parse RSS feeds, returning candidate articles"""
    if not feedparser:
        log.warning("feedparser not available, skipping RSS feeds")
        return []

    log.info("--- Fetching RSS Feed Candidates ---")
    feeds = [f for f in RSS_FEEDS if f["priority"] == "high"] if RSS_CONFIG["use_high_priority_only"] else RSS_FEEDS
    log.info(f"Using {len(feeds)} RSS feeds (high priority only: {RSS_CONFIG['use_high_priority_only']})")

    cutoff_time = datetime.now(timezone.utc) - timedelta(hours=DISCOVERY_HOURS_WINDOW)
    all_entries = []
    seen_urls = set()
    seen_titles = set()

    for feed_info in feeds:
        try:
            feed = feedparser.parse(feed_info["url"])
            if feed.bozo:
                log.warning(f"Feed parsing warning for {feed_info['name']}: {feed.bozo_exception}")

            for entry in feed.entries[:RSS_CONFIG["max_entries_per_feed"]]:
                # Parse published date
                published = None
                if hasattr(entry, "published_parsed") and entry.published_parsed:
                    try:
                        published = datetime(*entry.published_parsed[:6], tzinfo=timezone.utc)
                    except Exception:
                        pass

                # Filter by age
                if published and published < cutoff_time:
                    continue

                title = entry.get("title", "").strip()
                link = entry.get("link", "").strip()

                if not title or not link:
                    continue

                # Deduplicate by URL and title
                if link in seen_urls:
                    continue
                normalized_title = title.lower().strip()
                if normalized_title in seen_titles:
                    continue

                seen_urls.add(link)
                seen_titles.add(normalized_title)

                # Generate unique ID
                entry_id = hashlib.md5(link.encode()).hexdigest()[:16]

                all_entries.append({
                    "id": entry_id,
                    "title": title,
                    "url": link,
                    "source": feed_info["name"],
                    "published": published.isoformat() if published else None,
                })

            log.info(f"✓ Fetched {len([e for e in all_entries if e['source'] == feed_info['name']])} from {feed_info['name']}")
        except Exception as e:
            log.error(f"Failed to fetch {feed_info['name']}: {e}")

    # Sort by recency
    all_entries.sort(
        key=lambda e: e["published"] if e["published"] else "",
        reverse=True
    )

    log.info(f"Total RSS entries fetched: {len(all_entries)}")
    return all_entries

# -------- Manual Queue Functions --------
MANUAL_QUEUE_FILE = "manual_queue_romantasy.txt"

def fetch_manual_queue_candidates() -> List[Dict[str, Any]]:
    """Fetch candidates from manual queue file (one URL or topic per line)"""
    if not os.path.exists(MANUAL_QUEUE_FILE):
        # Create empty file with instructions
        with open(MANUAL_QUEUE_FILE, 'w') as f:
            f.write("# Manual Idea Queue - Add one URL or topic per line\n")
            f.write("# Lines starting with # are ignored\n")
            f.write("# After processing, entries will be commented out automatically\n\n")
        log.info(f"Created {MANUAL_QUEUE_FILE}")
        return []

    log.info("--- Fetching Manual Queue Candidates ---")
    candidates = []
    lines_to_keep = []

    with open(MANUAL_QUEUE_FILE, 'r') as f:
        lines = f.readlines()

    for line in lines:
        stripped = line.strip()

        # Keep comments and empty lines as-is
        if not stripped or stripped.startswith('#'):
            lines_to_keep.append(line)
            continue

        # Process this entry
        entry_id = f"manual_{hash(stripped) & 0xFFFFFFFF:08x}"

        # Determine if it's a URL or just a topic
        if stripped.startswith('http://') or stripped.startswith('https://'):
            url = stripped
            title = stripped  # Will extract title when fetching
        else:
            # It's a topic, not a URL
            url = None
            title = stripped

        candidates.append({
            "id": entry_id,
            "title": title,
            "url": url,
            "source": "Manual Queue",
            "published": datetime.now(timezone.utc).isoformat(),
        })

        # Comment out this line (mark as processed)
        lines_to_keep.append(f"# [PROCESSED] {stripped}\n")

    # Write back the file with processed entries commented out
    if candidates:
        with open(MANUAL_QUEUE_FILE, 'w') as f:
            f.writelines(lines_to_keep)
        log.info(f"✓ Fetched {len(candidates)} from Manual Queue (entries marked as processed)")
    else:
        log.info("No entries in manual queue")

    return candidates

# -------- JSON helpers --------
def extract_json(s: str) -> Any:
    s = s.strip()
    m = re.search(r'<json>(.*?)</json>', s, re.DOTALL | re.IGNORECASE)
    if m: s = m.group(1)
    m = re.search(r'```json\s*(\{.*?\}|\[.*?\])\s*```', s, re.DOTALL | re.IGNORECASE)
    if m: s = m.group(1)
    if s.startswith("{") or s.startswith("["):
        try: return json.loads(s)
        except Exception: pass
    start = s.find("{"); end = s.rfind("}")
    if start != -1 and end != -1 and end > start:
        try: return json.loads(s[start:end+1])
        except Exception: return s
    return s

def _expect_dict(d: Any, step: str) -> Dict[str, Any]:
    if not isinstance(d, dict):
        log.error(f"{step} returned non-dict: {str(d)[:500]}")
        return {}
    return d

# -------- API calling --------
def _call_openai(model: str, prompt: str, json_mode: bool = False, use_web_search: bool = False) -> Any:
    kwargs = {"model": model, "messages": [{"role":"user","content":prompt}]}
    if json_mode: kwargs["response_format"] = {"type":"json_object"}
    resp = client.chat.completions.create(**kwargs)
    content = (resp.choices[0].message.content or "").strip()
    return extract_json(content) if json_mode else content

def _call_anthropic(model: str, prompt: str, json_mode: bool = False) -> Any:
    system = "You are a helpful assistant. Follow instructions precisely."
    if json_mode:
        system += " You MUST wrap your entire JSON response in <json></json> tags. Ensure all JSON is valid with proper escaping."
    
    max_tokens = 4096 
    
    resp = anthropic_client.messages.create(
        model=model, system=system, max_tokens=max_tokens,
        messages=[{"role": "user", "content": prompt}]
    )
    content = resp.content[0].text if resp.content else ""
    
    if json_mode:
        m = re.search(r"<json>(.*?)</json>", content, re.DOTALL | re.IGNORECASE)
        if m:
            json_str = m.group(1).strip()
            try:
                return json.loads(json_str)
            except json.JSONDecodeError:
                log.warning(f"JSON parsing failed, trying with strict=False")
                try:
                    return json.loads(json_str, strict=False)
                except Exception as e:
                     log.warning(f"All JSON parsing attempts failed: {e}")
        
        log.error(f"Could not extract JSON from Anthropic. Preview: {content[:200]}")
        return {"error": "json_parse_failed"}
    
    return content

def call(model_key: str, prompt: str, json_mode: bool = True, use_web_search: bool = False) -> Any:
    model = MODEL_MAP.get(model_key, "gpt-5-mini")
    log.info(f"→ {model_key} [{model}]")
    for attempt in range(API_MAX_RETRIES):
        try:
            if model.startswith("claude-"):
                result = _call_anthropic(model, prompt, json_mode)
            else:
                result = _call_openai(model, prompt, json_mode, use_web_search)
            log.info(f"✓ {model_key}")
            return result
        except Exception as e:
            log.warning(f"API error ({type(e).__name__}). Retry in {2**attempt}s...")
            time.sleep(2 ** attempt)
    raise RuntimeError(f"Failed {model_key} after {API_MAX_RETRIES} retries")

# -------- URL helpers --------
def looks_like_url(s: str) -> bool:
    try:
        u = urlparse(s)
        return bool(u.scheme and u.netloc)
    except Exception: return False

def url_to_topic(url: str) -> tuple[str, Optional[str]]:
    if 'reddit.com' in url and reddit_client:
        try:
            match = re.search(r'/comments/([a-z0-9]+)/', url)
            if match:
                post_id = match.group(1)
                submission = reddit_client.submission(id=post_id)
                log.info(f"✓ Reddit API: {submission.title}")
                selftext = submission.selftext if submission.selftext else None
                return submission.title, selftext
        except Exception as e:
            log.warning(f"Reddit API fetch failed: {e}, falling back to scraping")
    
    try:
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
        log.info(f"Fetching page title from: {url}")
        response = requests.get(url, headers=headers, timeout=15)
        response.raise_for_status()
        soup = BeautifulSoup(response.content, 'html.parser')
        
        if title_tag := soup.find('title'):
            title = title_tag.get_text().strip()
            if title.lower() not in ['reddit - the heart of the internet', 'reddit', 'twitter', 'x']:
                title = re.sub(r'\s*:\s*r/\w+\s*$', '', title)
                title = re.sub(r'\s*/\s*(Twitter|X)\s*$', '', title, flags=re.IGNORECASE)
                title = re.sub(r'\s+', ' ', title).strip()
                if title: return title, None
    except Exception as e:
        log.warning(f"Could not fetch page title ({type(e).__name__}): {e}")
    
    path = urlparse(url).path.strip('/')
    slug = path.split('/')[-1] if path else url
    slug = re.sub(r'["\']', '', slug).split("?")[0].replace('_', ' ').replace('-', ' ')
    topic = slug.strip()
    log.info(f"Parsed from URL: {topic}")
    return topic, None

# -------- WordPress --------
WP_URL = os.getenv("WP_URL", "").rstrip("/")
WP_USERNAME = os.getenv("WP_USERNAME", "")
WP_APP_PASSWORD = os.getenv("WP_APP_PASSWORD", "")
WP_PUBLISH_STATUS = os.getenv("WP_PUBLISH_STATUS", "draft")
WP_AUTHOR_ID = int(os.getenv("WP_AUTHOR_ID", "1"))
ALLOW_CREATE_CATEGORIES = os.getenv("ALLOW_CREATE_CATEGORIES", "false").lower() == "true"
META_DESC_MAX_LENGTH = 150
WP_CATEGORIES_CACHE: Dict[str, int] = {}

def wp_auth() -> HTTPBasicAuth:
    if not (WP_URL and WP_USERNAME and WP_APP_PASSWORD):
        raise RuntimeError("WP credentials missing")
    return HTTPBasicAuth(WP_USERNAME, WP_APP_PASSWORD)

def ensure_category_ids(categories: List[str]) -> List[int]:
    global WP_CATEGORIES_CACHE
    if not WP_CATEGORIES_CACHE:
        try:
            r = requests.get(f"{WP_URL}/wp-json/wp/v2/categories", params={"per_page": 100}, auth=wp_auth(), timeout=30)
            r.raise_for_status()
            for cat in r.json(): WP_CATEGORIES_CACHE[cat['name'].lower()] = cat['id']
            log.info(f"Cached {len(WP_CATEGORIES_CACHE)} WP categories")
        except Exception as e: log.error(f"Category fetch failed: {e}")
    
    ids = []
    for name in categories:
        name = name.strip()
        if not name: continue
        if name.lower() in WP_CATEGORIES_CACHE:
            ids.append(WP_CATEGORIES_CACHE[name.lower()])
            continue
        if ALLOW_CREATE_CATEGORIES:
            try:
                rc = requests.post(f"{WP_URL}/wp-json/wp/v2/categories", json={"name": name}, auth=wp_auth(), timeout=30)
                rc.raise_for_status()
                new_cat = rc.json()
                WP_CATEGORIES_CACHE[new_cat['name'].lower()] = new_cat['id']
                ids.append(new_cat["id"])
            except requests.RequestException as e:
                log.error(f"Category create failed '{name}': {e}")
        else:
            log.warning(f"Category '{name}' not found, creation disabled")
    return ids

def build_yoast_meta(seo_pack: dict) -> dict:
    meta_desc = (seo_pack.get("meta_description") or "")[:META_DESC_MAX_LENGTH]
    return {
        "_yoast_wpseo_title": seo_pack.get("seo_title", "") or seo_pack.get("title", ""),
        "_yoast_wpseo_metadesc": meta_desc,
        "_yoast_wpseo_focuskw": "" 
    }

def publish_to_wordpress(title: str, content_html: str, slug: str, 
                        excerpt: str, seo_pack: dict, categories: List[str]) -> Dict[str, Any]:
    payload = {
        "title": title, "status": WP_PUBLISH_STATUS, "slug": slug,
        "content": content_html, "excerpt": excerpt, "author": WP_AUTHOR_ID,
        "categories": ensure_category_ids(categories),
        "meta": build_yoast_meta(seo_pack)
    }
    
    log.info("Publishing IDEA STUB to WordPress...")
    try:
        r = requests.post(f"{WP_URL}/wp-json/wp/v2/posts", 
                         json=payload, auth=wp_auth(), timeout=60)
        r.raise_for_status()
        post = r.json()
        log.info(f"WP Draft ID: {post.get('id')} | {post.get('link')}")
        return post
    except requests.RequestException as e:
        log.error(f"WP publish failed: {e}")
        raise

# -------- Reddit Auto-Discovery Functions --------
def load_processed_ids() -> set[str]:
    """Loads previously processed Reddit post IDs from a file."""
    if not os.path.exists(PROCESSED_IDS_FILE):
        return set()
    try:
        with open(PROCESSED_IDS_FILE, "r") as f:
            return {line.strip() for line in f if line.strip()}
    except IOError as e:
        log.error(f"Could not read processed IDs file: {e}")
        return set()

def save_processed_id(reddit_id: str):
    """Appends a new Reddit post ID to the processed file."""
    try:
        with open(PROCESSED_IDS_FILE, "a") as f:
            f.write(f"{reddit_id}\n")
    except IOError as e:
        log.error(f"Could not write to processed IDs file: {e}")

def agent_relevance_filter(title: str) -> Optional[Dict[str, Any]]:
    """Uses an AI agent to score a post title for relevance and SEO potential."""
    try:
        # **FIXED: Now passes all required format variables**
        prompt = P.MELISSA_RELEVANCE_FILTER_PROMPT.format(
            title=title,
            NEW_PILLARS=P.NEW_PILLARS
        )
        result = call("relevance_filter", prompt)
        if result and result.get("is_good_candidate"):
            return result
    except Exception as e:
        log.warning(f"Relevance filter agent failed for title '{title[:50]}...': {e}")
    return None

def fetch_and_filter_reddit_candidates() -> List[Dict[str, Any]]:
    """
    Fetches hot posts, then uses an AI filter to select the best candidates.
    """
    if not reddit_client:
        log.error("Reddit client not initialized. Cannot fetch candidates.")
        return []

    log.info("--- Starting Reddit Auto-Discovery (Advertising Investment & Accountability v8.0) ---")
    raw_candidates = []
    processed_ids = load_processed_ids()
    cutoff_ts = (datetime.now(timezone.utc) - timedelta(hours=DISCOVERY_HOURS_WINDOW)).timestamp()

    log.info(f"Scanning {len(SUBREDDIT_CONFIG)} subreddits with dynamic thresholds...")
    for sub_name, min_score in SUBREDDIT_CONFIG.items():
        try:
            subreddit = reddit_client.subreddit(sub_name)
            for post in subreddit.hot(limit=30):
                if post.created_utc < cutoff_ts:
                    break
                
                if post.stickied or post.score < min_score or post.id in processed_ids:
                    continue
                
                raw_candidates.append({
                    "id": post.id,
                    "title": post.title,
                    "url": f"https://www.reddit.com{post.permalink}",
                    "score": post.score,
                    "subreddit": sub_name
                })
                processed_ids.add(post.id)
        except Exception as e:
            log.warning(f"Failed to fetch from r/{sub_name}: {e}")
        time.sleep(1) 

    log.info(f"Found {len(raw_candidates)} raw candidates. Now running AI relevance filter (Advertising Pillars)...")
    
    viable_candidates = []
    for post in raw_candidates:
        filter_result = agent_relevance_filter(post["title"])
        if filter_result:
            post.update(filter_result)
            ai_relevance = post.get("relevance_score", 0.0)
            popularity = min(1.0, post['score'] / 3000)
            # Use AI relevance as primary signal, popularity as small bonus
            post["ranking_score"] = min(1.0, ai_relevance + (popularity * 0.05))
            
            viable_candidates.append(post)
            log.info(f"  ✓ Accepted: 'r/{post['subreddit']}' - '{post['title'][:60]}' (Rank: {post['ranking_score']:.2f})")
            log.info(f"    Reason: {filter_result.get('reason')}")
        else:
            log.info(f"  ✗ Rejected: 'r/{post['subreddit']}' - '{post['title'][:60]}'")
            
    log.info(f"AI filter approved {len(viable_candidates)} candidates for processing.")
    return viable_candidates

# ======== NEW SIMPLIFIED PIPELINE (MELISSA E-E-A-T) ========
def run_idea_factory_stub(topic_or_url: str) -> Dict[str, Any]:
    out: Dict[str, Any] = {"input": topic_or_url, "ts": datetime.now(timezone.utc).isoformat()}
    
    log.info("="*69)
    log.info("Melissa E-E-A-T Idea Factory Stub Generator (v7.3)")
    log.info(f"Input: {topic_or_url}")
    log.info("="*69)
    
    if looks_like_url(topic_or_url):
        topic, selftext = url_to_topic(topic_or_url)
    else:
        topic = topic_or_url
    
    log.info(f"Topic: {topic}")
    out["topic"] = topic
    
    # 1) Generate Angles, Select Best, and Generate Research Plan (1 call)
    # **FIXED: Now passes all required format variables**
    angle_plan_prompt = P.MELISSA_ANGLE_AND_PLAN_PROMPT.format(
        topic=topic,
        BLOG_THESIS=P.BLOG_THESIS,
        EXPERT_PERSONA_CONTEXT=P.EXPERT_PERSONA_CONTEXT,
        NEW_PILLARS=P.NEW_PILLARS,
        NEW_FORMATS=P.NEW_FORMATS
    )
    angle_plan_result = call("angle_and_plan", angle_plan_prompt)
    out.update(_expect_dict(angle_plan_result, "Angle & Plan"))
    
    winning_angle = out.get("winning_angle", {})
    
    log.info(f"→ {len(out.get('all_angles', []))} angles generated.")
    log.info(f"→ Selected Angle: {winning_angle.get('helpful_angle')}")
    log.info(f"→ Pillar/Format: {winning_angle.get('pillar')} / {winning_angle.get('format')}")
    
    if "deep_research_prompt" not in out:
        log.error("Failed to generate deep research prompt.")
    
    # 2) Category
    pillar_to_category = {
        "Romantasy Craft & Structure": "Craft & Writing",
        "Market Trends & Publishing": "Publishing & Market",
        "Reader Psychology & Audience": "Reader Psychology",
    }
    pillar_name = winning_angle.get("pillar", "Craft & Writing")
    out["category_name"] = pillar_to_category.get(pillar_name, "Craft & Writing")
    log.info(f"→ Pillar-based Category: {out['category_name']}")
    
    # 3) Save & Publish STUB
    
    slug_base = winning_angle.get('helpful_angle', 'new-idea')
    slug_base = slug_base.lower().replace(" ", "-")
    slug_base = re.sub(r'[^a-z0-9-]', '', slug_base)[:60] # Clean slug
    
    fname = f"IDEA_{slug_base}_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}.json"
    try:
        with open(fname, "w", encoding="utf-8") as f:
            json.dump(out, f, indent=2)
        out["idea_file"] = fname
        log.info(f"→ Idea packet saved: {fname}")
    except Exception as e:
        log.error(f"Failed to save local JSON file: {e}")

    # Print output to console instead of WordPress
    log.info("=" * 80)
    log.info("✓ ROMANTASY WRITING ADVICE IDEA GENERATED")
    log.info("=" * 80)

    print("\n" + "=" * 80)
    print("🎯 WINNING ANGLE")
    print("=" * 80)
    print(f"Pillar: {winning_angle.get('pillar', 'N/A')}")
    print(f"Format: {winning_angle.get('format', 'N/A')}")
    print(f"Angle: {winning_angle.get('helpful_angle', 'N/A')}")
    print(f"Persona: {winning_angle.get('expert_persona', 'N/A')}")

    # Free guide section (if present)
    free_guide_idea = out.get('free_guide_idea')
    free_guide_description = out.get('free_guide_description')

    if free_guide_idea and free_guide_description:
        print("\n" + "=" * 80)
        print("💎 FREE GUIDE IDEA (Newsletter Lead Magnet)")
        print("=" * 80)
        print(f"Title: {free_guide_idea}")
        print(f"Description: {free_guide_description}")

    # Deep research prompt
    print("\n" + "=" * 80)
    print("📚 DEEP RESEARCH PROMPT")
    print("=" * 80)
    print(out.get('deep_research_prompt', 'Error: Prompt not generated.'))

    # All angles considered
    print("\n" + "=" * 80)
    print("💡 ALL ANGLES CONSIDERED")
    print("=" * 80)
    for i, angle in enumerate(out.get('all_angles', []), 1):
        print(f"\nAngle {i}:")
        print(f"  Pillar: {angle.get('pillar')}")
        print(f"  Format: {angle.get('format')}")
        print(f"  Angle: {angle.get('helpful_angle')}")

    print("\n" + "=" * 80)
    log.info(f"Idea saved to: {fname}")
    log.info("="*69)
    return out

def main():
    parser = argparse.ArgumentParser(description="Melissa E-E-A-T Idea Factory v8.0 (Advertising Investment Focus)")
    parser.add_argument("topic_or_url", nargs='?', default=None, help="Optional: A specific topic or URL to process.")

    args = parser.parse_args()

    if args.topic_or_url:
        log.info(f"--- Running in MANUAL mode for: {args.topic_or_url} ---")
        run_idea_factory_stub(args.topic_or_url)
    else:
        log.info("--- Running in AUTO-DISCOVERY mode (Reddit + RSS) ---")

        # 1. Fetch Reddit candidates
        reddit_candidates = fetch_and_filter_reddit_candidates()
        log.info(f"Reddit candidates after filter: {len(reddit_candidates)}")

        # 2. Fetch RSS candidates
        rss_entries = fetch_rss_candidates()

        # 3. Run RSS entries through the same relevance filter
        rss_candidates = []
        for entry in rss_entries:
            filter_result = agent_relevance_filter(entry["title"])
            if filter_result and filter_result.get("is_good_candidate"):
                # Add to candidates with ranking (pure AI score for RSS)
                ai_relevance = filter_result.get("relevance_score", 0.0)
                rss_candidates.append({
                    "id": entry["id"],
                    "title": entry["title"],
                    "url": entry["url"],
                    "score": 0,  # RSS doesn't have popularity score
                    "subreddit": entry["source"],  # Use RSS source as "subreddit" for display
                    "ranking_score": ai_relevance,  # Pure AI score
                    "relevance_score": ai_relevance,
                    "reason": filter_result.get("reason"),
                    "source_type": "RSS"
                })
                log.info(f"  ✓ RSS Accepted: '{entry['source']}' - '{entry['title'][:60]}' (Score: {ai_relevance:.2f})")
            else:
                log.debug(f"  ✗ RSS Rejected: '{entry['source']}' - '{entry['title'][:60]}'")

        log.info(f"RSS candidates after filter: {len(rss_candidates)}")

        # 3b. Fetch Manual Queue candidates
        manual_entries = fetch_manual_queue_candidates()

        # 3c. Run Manual Queue entries through the same relevance filter
        manual_candidates = []
        for entry in manual_entries:
            filter_result = agent_relevance_filter(entry["title"])
            if filter_result and filter_result.get("is_good_candidate"):
                # Add to candidates with ranking (pure AI score for manual)
                ai_relevance = filter_result.get("relevance_score", 0.0)
                manual_candidates.append({
                    "id": entry["id"],
                    "title": entry["title"],
                    "url": entry["url"] if entry["url"] else f"manual_topic_{entry['id']}",
                    "score": 0,  # Manual doesn't have popularity score
                    "subreddit": "Manual Queue",  # Use "Manual Queue" as source
                    "ranking_score": ai_relevance,  # Pure AI score
                    "relevance_score": ai_relevance,
                    "reason": filter_result.get("reason"),
                    "source_type": "Manual"
                })
                log.info(f"  ✓ Manual Accepted: '{entry['title'][:60]}' (Score: {ai_relevance:.2f})")
            else:
                log.debug(f"  ✗ Manual Rejected: '{entry['title'][:60]}'")

        log.info(f"Manual Queue candidates after filter: {len(manual_candidates)}")

        # 4. Combine all candidates
        all_candidates = reddit_candidates + rss_candidates + manual_candidates

        if not all_candidates:
            log.info("No candidates from Reddit, RSS, or Manual Queue passed the AI filter. Exiting.")
            return

        # 5. Filter by minimum quality score
        final_selection = [
            post for post in all_candidates
            if post.get("ranking_score", 0) >= MIN_PROCESSING_SCORE
        ]

        final_selection.sort(key=lambda x: x['ranking_score'], reverse=True)

        if not final_selection:
            log.info(f"No posts met the minimum quality score of {MIN_PROCESSING_SCORE}. Exiting.")
            return

        log.info(f"Selected {len(final_selection)} items for processing (Reddit: {len([p for p in final_selection if p.get('source_type') != 'RSS'])}, RSS: {len([p for p in final_selection if p.get('source_type') == 'RSS'])})")

        # 6. Process each candidate
        for i, post in enumerate(final_selection):
            source_type = post.get("source_type", "Reddit")
            log.info(f"\n{'='*25} PROCESSING {source_type} ITEM {i+1}/{len(final_selection)} {'='*25}")
            log.info(f"Source: {post['subreddit']}")
            log.info(f"Title: {post['title']}")
            log.info(f"URL: {post['url']}")
            if source_type == "Reddit":
                log.info(f"Ranking Score: {post['ranking_score']:.2f} (Reddit: {post['score']}, AI: {post['relevance_score']:.2f})")
            else:
                log.info(f"Ranking Score: {post['ranking_score']:.2f} (AI: {post['relevance_score']:.2f})")

            try:
                run_idea_factory_stub(post['url'])
                save_processed_id(post['id'])
                log.info(f"Successfully processed and saved ID: {post['id']}")
            except Exception as e:
                log.error(f"PIPELINE FAILED for '{post['title']}'. Error: {e}", exc_info=True)

            time.sleep(5)
            
    log.info("--- Pipeline run finished. ---")


if __name__ == "__main__":
    main()