# main.py
# VERSION 8.0: "Melissa" E-E-A-T Idea Factory (Advertising Investment & Accountability Focus)
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

import prompts as P

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

# --- Reddit Auto-Discovery Configuration ---
SUBREDDIT_CONFIG = {
    # --- Pillar 1 & 2: Advertising Accountability & Strategy ---
    "adops": 25,              "adtech": 10,             "advertising": 100,
    "PPC": 150,               "marketing": 300,         "socialmedia": 100,
    "digital_marketing": 200, "SEO": 300,
    "BusinessOfMedia": 10,    "publishing": 50,         "agency": 50,
    "strategy": 25,           "branding": 100,
    
    # --- Pillar 3: Media Analysis, AI & Automation ---
    "datascience": 200,       "martech": 50,
    "PublicRelations": 75,    "TechSEO": 25,
    "learnpython": 100,       "MachineLearning": 200,   
    "Automation": 200,        "fintech": 50,            "privacy": 200,
}

HOURS_WINDOW = 24
MIN_PROCESSING_SCORE = 0.65  # Lowered from 0.70 to catch more good Reddit posts
PROCESSED_IDS_FILE = "processed_posts.txt"

# --- RSS Feed Sources Configuration ---
RSS_FEEDS = [
    # Pillar 1: Media Accountability & Performance
    {"name": "AdExchanger", "url": "https://adexchanger.com/feed/", "priority": "high"},
    {"name": "AdAge", "url": "https://adage.com/rss-feed", "priority": "high"},
    {"name": "Digiday", "url": "https://digiday.com/feed/", "priority": "high"},
    {"name": "MediaPost - Online Media", "url": "https://www.mediapost.com/publications/rss/online-media-daily.xml", "priority": "medium"},
    {"name": "MediaPost - Research", "url": "https://www.mediapost.com/publications/rss/research.xml", "priority": "medium"},

    # Pillar 2: Advertising Strategy & Investment
    {"name": "The Drum", "url": "https://www.thedrum.com/rss/news/all", "priority": "high"},
    {"name": "MediaPost - Agency Daily", "url": "https://www.mediapost.com/publications/rss/agency-daily.xml", "priority": "high"},
    # Removed Search Engine Land - too much SEO/organic content that gets filtered out
    {"name": "MediaPost - Marketing Daily", "url": "https://www.mediapost.com/publications/rss/marketing-daily.xml", "priority": "medium"},
    {"name": "AdAge - Brand Marketing", "url": "https://adage.com/section/brand-marketing/rss", "priority": "medium"},

    # Pillar 3: Advertising Analytics & Automation
    # Removed MarTech - too general, not advertising-specific enough
    {"name": "MediaPost - Data & Targeting", "url": "https://www.mediapost.com/publications/rss/data-and-targeting-insider.xml", "priority": "high"},
    {"name": "MediaPost - Social Media", "url": "https://www.mediapost.com/publications/rss/social-media-marketing-daily.xml", "priority": "medium"},
    {"name": "MediaPost - Mobile", "url": "https://www.mediapost.com/publications/rss/mobile-marketing-daily.xml", "priority": "medium"},
]

RSS_CONFIG = {
    "max_entries_per_feed": 20,
    "max_age_hours": 48,
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

    cutoff_time = datetime.now(timezone.utc) - timedelta(hours=RSS_CONFIG["max_age_hours"])
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

    log.info("--- Starting Reddit Auto-Discovery (Comms & Ad Focus v7.3) ---")
    raw_candidates = []
    processed_ids = load_processed_ids()
    cutoff_ts = (datetime.now(timezone.utc) - timedelta(hours=HOURS_WINDOW)).timestamp()

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
        "Media Accountability & Performance": "Media Accountability",
        "Advertising Strategy & Investment": "Ad Strategy",
        "Media Analysis, AI & Automation": "Ad-Tech & AI",
    }
    pillar_name = winning_angle.get("pillar", "Ad Strategy")
    out["category_name"] = pillar_to_category.get(pillar_name, "Ad Strategy")
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
    
    if WP_URL and WP_USERNAME and WP_APP_PASSWORD:
        log.info("--- Publishing IDEA STUB to WordPress ---")
        
        try:
            import html
            escape = html.escape
        except ImportError:
            log.warning("html module not found. Will not escape <pre> content.")
            escape = lambda s: s 

        angles_json = escape(json.dumps(out.get('all_angles', []), indent=2))
        winning_angle_html = f"""
    <p><strong>Pillar:</strong> {escape(winning_angle.get('pillar', 'N/A'))}</p>
    <p><strong>Format:</strong> {escape(winning_angle.get('format', 'N/A'))}</p>
    <p><strong>Angle:</strong> {escape(winning_angle.get('helpful_angle', 'N/A'))}</p>
    <p><strong>Persona:</strong> {escape(winning_angle.get('expert_persona', 'N/A'))}</p>
"""
        research_prompt_escaped = escape(out.get('deep_research_prompt', 'Error: Prompt not generated.'))
        
        dev_notes_html = f"""
<details open>
    <summary><strong>Generation &amp; Angle Analysis (Advertising E-E-A-T)</strong></summary>
    
    <p><strong>Original Source:</strong> <a href="{out['input']}" target="_blank" rel="noopener noreferrer">{escape(out['topic'])}</a></p>
    
    <h3>Winning Angle:</h3>
    {winning_angle_html}

    <hr />

    <h3>Deep Research Prompt (Copy This)</h3>
    <pre style="background-color:#f5f5f5; border:1px solid #ccc; padding:10px; border-radius:4px; white-space: pre-wrap; word-wrap: break-word;">{research_prompt_escaped}</pre>
    
    <hr />
    
    <h3>All Angles Considered:</h3>
    <pre style="background-color:#f5f5f5; border:1px solid #ccc; padding:10px; border-radius:4px; white-space: pre-wrap; word-wrap: break-word;">{angles_json}</pre>

</details>
"""
        
        post_title = f"[IDEA] {winning_angle.get('helpful_angle', out.get('topic', 'New Post Idea'))}"
        excerpt = f"Pillar: {winning_angle.get('pillar', 'N/A')} | Format: {winning_angle.get('format', 'N/A')}"
        
        wp_post = publish_to_wordpress(
            title=post_title,
            content_html=dev_notes_html,
            slug=f"idea-{slug_base}",
            excerpt=excerpt,
            seo_pack={"title": post_title, "meta_description": excerpt},
            categories=[out.get("category_name", "Ad Strategy")]
        )
        out["wordpress"] = {
            "id": wp_post.get("id"),
            "link": wp_post.get("link"),
            "status": wp_post.get("status")
        }
    
    log.info("="*69)
    log.info("✓ ADVERTISING E-E-A-T IDEA STUB GENERATED")
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

        # 4. Combine all candidates
        all_candidates = reddit_candidates + rss_candidates

        if not all_candidates:
            log.info("No candidates from Reddit or RSS passed the AI filter. Exiting.")
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