#!/usr/bin/env python3
# automate_romantasy_social_batch.py
# Enhanced batch social media automation with multi-topic workflow

import os
import sys
import json
import smtplib
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional, Tuple
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.image import MIMEImage

import requests
import anthropic

try:
    from dotenv import load_dotenv
    load_dotenv()
except Exception:
    pass

try:
    from openai import OpenAI
    OPENAI_AVAILABLE = True
except ImportError:
    OPENAI_AVAILABLE = False
    print("INFO: openai not installed. Web search unavailable.")

try:
    from google import genai
    from google.genai import types
    GENAI_AVAILABLE = True
except ImportError:
    GENAI_AVAILABLE = False
    print("WARNING: google-genai not installed. Image generation unavailable.")

try:
    import tweepy
    TWEEPY_AVAILABLE = True
except ImportError:
    TWEEPY_AVAILABLE = False
    print("INFO: tweepy not installed. Twitter auto-posting unavailable.")

# --- Configuration ---
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
APILAYER_API_KEY = os.getenv("APILAYER_API_KEY")

TWITTER_API_KEY = os.getenv("TWITTER_API_KEY")
TWITTER_API_SECRET = os.getenv("TWITTER_API_SECRET")
TWITTER_ACCESS_TOKEN = os.getenv("TWITTER_ACCESS_TOKEN")
TWITTER_ACCESS_SECRET = os.getenv("TWITTER_ACCESS_SECRET")

META_ACCESS_TOKEN = os.getenv("META_ACCESS_TOKEN")
META_USER_ID = os.getenv("META_USER_ID")

PINTEREST_ACCESS_TOKEN = os.getenv("PINTEREST_ACCESS_TOKEN")
PINTEREST_BOARD_ID = os.getenv("PINTEREST_BOARD_ID")

EMAIL_FROM = os.getenv("EMAIL_FROM", "")
EMAIL_TO = os.getenv("EMAIL_TO", "")
SMTP_HOST = os.getenv("SMTP_HOST", "smtp.gmail.com")
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
SMTP_USER = os.getenv("SMTP_USER", "")
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD", "")

if not ANTHROPIC_API_KEY:
    print("ERROR: ANTHROPIC_API_KEY not configured")
    sys.exit(1)

anthropic_client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
openai_client = None
if OPENAI_AVAILABLE and OPENAI_API_KEY:
    openai_client = OpenAI(api_key=OPENAI_API_KEY)

PLATFORM_LIMITS = {
    "twitter": 280,
    "threads": 500,
    "pinterest": 500,
    "instagram": 2200
}

# Session management
SESSION_DIR = "social_sessions"
PERFORMANCE_DB = "post_performance.json"

# ==================== HELPER FUNCTIONS ====================

def prompt_user(message: str, options: List[str]) -> str:
    """Interactive prompt with numbered options"""
    print(f"\n{message}")
    for i, option in enumerate(options, 1):
        print(f"  {i}. {option}")

    while True:
        try:
            choice = input("\nYour choice (number): ").strip()
            choice_idx = int(choice) - 1
            if 0 <= choice_idx < len(options):
                return options[choice_idx]
            print("Invalid choice. Please try again.")
        except (ValueError, KeyboardInterrupt):
            print("\nPlease enter a valid number.")

def prompt_multi_select(message: str, options: List[str]) -> List[int]:
    """Multi-select prompt - returns list of selected indices"""
    print(f"\n{message}")
    for i, option in enumerate(options, 1):
        print(f"  {i}. {option}")

    print("\nEnter numbers separated by commas (e.g., 1,3,5) or 'all':")
    while True:
        try:
            choice = input("Your choices: ").strip().lower()
            if choice == "all":
                return list(range(len(options)))

            indices = [int(x.strip()) - 1 for x in choice.split(",")]
            if all(0 <= idx < len(options) for idx in indices):
                return indices
            print("Invalid selection. Please try again.")
        except (ValueError, KeyboardInterrupt):
            print("\nPlease enter valid numbers separated by commas.")

def confirm_action(message: str) -> bool:
    """Ask user to confirm"""
    response = input(f"\n{message} (y/n): ").strip().lower()
    return response in ['y', 'yes']

def get_multiline_input(prompt_text: str) -> str:
    """Get multi-line text input (press Enter twice to finish)"""
    print(f"\n{prompt_text}")
    print("(Press Enter twice when done)\n")

    lines = []
    print(">>> ", end="", flush=True)
    while True:
        try:
            line = input()
            if line.strip() == "" and len(lines) > 0 and lines[-1].strip() == "":
                break
            lines.append(line)
            print(">>> ", end="", flush=True)
        except EOFError:
            break

    return "\n".join(lines).strip()

# ==================== FEATURE 1: HASHTAG GENERATION ====================

def generate_hashtags(topic: str, platform: str, count: int = 10) -> Dict[str, List[str]]:
    """Generate strategic hashtags for a topic and platform"""

    platform_guidelines = {
        "twitter": "Mix of trending + niche. Keep them short and specific.",
        "threads": "Use sparingly (3-5). Focus on community tags.",
        "pinterest": "Highly searchable keywords. 10-15 hashtags OK.",
        "instagram": "Mix of popular + niche. 15-30 hashtags recommended."
    }

    prompt = f"""You are a social media strategist for "Plot Brew," a romantasy writing advice platform.

**TOPIC:** {topic}
**PLATFORM:** {platform}

Generate strategic hashtags for this platform.

**Platform Guidelines:** {platform_guidelines.get(platform, "General hashtags")}

**Hashtag Strategy:**
- Mix of HIGH-TRAFFIC tags (competitive but discoverable)
- NICHE tags (lower traffic, highly targeted romantasy audience)
- COMMUNITY tags (BookTok, Bookstagram, writing communities)
- GENRE tags (romantasy, fantasy romance, etc.)

**For Romantasy Content:**
- Writing craft tags (#WritingTips, #AmWriting, #WritingCommunity)
- Genre tags (#Romantasy, #FantasyRomance, #BookTok)
- Niche craft tags (#CharacterDevelopment, #WorldBuilding, #WritingMagicSystems)
- Reader community tags (#BookstagramCommunity, #RomanceReaders)

Return ONLY this JSON format:

{{
  "high_traffic": ["#tag1", "#tag2", ...],
  "niche": ["#tag3", "#tag4", ...],
  "community": ["#tag5", "#tag6", ...],
  "recommended": ["#tag", "#tag", ...] // Your top {count} picks in priority order
}}
"""

    response = anthropic_client.messages.create(
        model="claude-sonnet-4-5",
        max_tokens=800,
        messages=[{"role": "user", "content": prompt}]
    )

    return extract_json(response.content[0].text)

# ==================== FEATURE 2: SESSION SAVE/RESUME ====================

def save_session(session_data: Dict, phase: str) -> str:
    """Save current session to resume later"""
    if not os.path.exists(SESSION_DIR):
        os.makedirs(SESSION_DIR)

    timestamp = datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')
    filename = f"{SESSION_DIR}/session_{timestamp}.json"

    session_data['current_phase'] = phase
    session_data['saved_at'] = datetime.now(timezone.utc).isoformat()

    with open(filename, 'w', encoding='utf-8') as f:
        json.dump(session_data, f, indent=2, ensure_ascii=False)

    return filename

def load_latest_session() -> Optional[Dict]:
    """Load most recent saved session"""
    if not os.path.exists(SESSION_DIR):
        return None

    sessions = [f for f in os.listdir(SESSION_DIR) if f.startswith('session_') and f.endswith('.json')]
    if not sessions:
        return None

    # Get most recent
    sessions.sort(reverse=True)
    latest = sessions[0]

    with open(os.path.join(SESSION_DIR, latest), 'r', encoding='utf-8') as f:
        return json.load(f)

def list_saved_sessions() -> List[Tuple[str, Dict]]:
    """List all saved sessions with metadata"""
    if not os.path.exists(SESSION_DIR):
        return []

    sessions = []
    for filename in os.listdir(SESSION_DIR):
        if filename.startswith('session_') and filename.endswith('.json'):
            filepath = os.path.join(SESSION_DIR, filename)
            with open(filepath, 'r', encoding='utf-8') as f:
                data = json.load(f)
                sessions.append((filename, data))

    sessions.sort(key=lambda x: x[1].get('saved_at', ''), reverse=True)
    return sessions

# ==================== FEATURE 3: A/B TESTING ====================

def draft_post_variations(topic: str, platform: str, research: Optional[str] = None, count: int = 3) -> List[str]:
    """Generate multiple post variations for A/B testing"""

    research_context = f"\n\n**RESEARCH CONTEXT:**\n{research}" if research else ""

    platform_specs = {
        "twitter": "280 chars max - Hook + craft insight + question",
        "threads": "500 chars max - Personal story + insights + community question",
        "pinterest": "500 chars - Educational, keyword-rich, list format",
        "instagram": "2200 chars max - Story-driven + 5-7 tips + hashtags"
    }

    prompt = f"""You are creating {count} different variations of a social media post for "Plot Brew."

**TOPIC:** {topic}{research_context}
**PLATFORM:** {platform} - {platform_specs.get(platform, "")}

**YOUR VOICE:**
- Personal and vulnerable (share writing journey)
- Celebratory of romantasy (treat it with intellectual respect)
- Community-focused ("we" language, not "you")
- Geeky enthusiasm about tropes and craft
- Relatable struggles of writing life

**CREATE {count} VARIATIONS with different approaches:**

1. **Variation 1 - Educational/How-To**
   Lead with practical tips, step-by-step approach

2. **Variation 2 - Personal Story/Vulnerable**
   Start with your own struggle or journey, then share the lesson

3. **Variation 3 - Provocative/Hot Take**
   Bold statement or controversial angle (but supportive), challenge assumptions

Return ONLY this JSON format:

{{
  "variations": [
    {{
      "style": "educational",
      "post": "Your post text here"
    }},
    {{
      "style": "personal",
      "post": "Your post text here"
    }},
    {{
      "style": "provocative",
      "post": "Your post text here"
    }}
  ]
}}
"""

    response = anthropic_client.messages.create(
        model="claude-sonnet-4-5",
        max_tokens=2000,
        messages=[{"role": "user", "content": prompt}]
    )

    result = extract_json(response.content[0].text)
    return result.get('variations', [])

def track_post_performance(topic: str, platform: str, variation_style: str, post_text: str):
    """Track which variations get selected for future learning"""
    if not os.path.exists(PERFORMANCE_DB):
        data = {"selections": []}
    else:
        with open(PERFORMANCE_DB, 'r') as f:
            data = json.load(f)

    data["selections"].append({
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "topic": topic,
        "platform": platform,
        "variation_style": variation_style,
        "post_length": len(post_text)
    })

    with open(PERFORMANCE_DB, 'w') as f:
        json.dump(data, f, indent=2)

def get_performance_insights() -> Dict:
    """Analyze historical performance to guide future content"""
    if not os.path.exists(PERFORMANCE_DB):
        return {"message": "No performance data yet"}

    with open(PERFORMANCE_DB, 'r') as f:
        data = json.load(f)

    selections = data.get("selections", [])
    if not selections:
        return {"message": "No selections tracked yet"}

    # Analyze which styles perform best per platform
    platform_styles = {}
    for sel in selections:
        platform = sel['platform']
        style = sel['variation_style']

        if platform not in platform_styles:
            platform_styles[platform] = {}

        platform_styles[platform][style] = platform_styles[platform].get(style, 0) + 1

    return {
        "total_posts": len(selections),
        "platform_style_preferences": platform_styles,
        "message": "This data shows which post styles you prefer per platform"
    }

# ==================== PHASE 1: TOPIC BRAINSTORMING ====================

def brainstorm_direct_topics(count: int = 5) -> List[Dict[str, str]]:
    """AI brainstorms topics from its own knowledge"""
    prompt = f"""You are a content strategist for "Plot Brew," a romantasy writing advice platform.

Brainstorm {count} specific, actionable writing advice topics for romantasy writers.

**Topic Guidelines:**
- Specific to romantasy genre (not generic writing advice)
- Actionable and practical
- Addresses craft, structure, or reader expectations
- Mix of different aspects: character work, plot, worldbuilding, tropes, market trends

Return ONLY this JSON format:

{{
  "topics": [
    {{
      "topic": "Topic title",
      "description": "One sentence explaining what this covers",
      "category": "craft/tropes/market/structure/etc"
    }},
    ...
  ]
}}
"""

    response = anthropic_client.messages.create(
        model="claude-sonnet-4-5",
        max_tokens=1500,
        messages=[{"role": "user", "content": prompt}]
    )

    result = extract_json(response.content[0].text)
    return result.get("topics", [])

def brainstorm_subreddit_topics(count: int = 5) -> List[Dict[str, str]]:
    """AI generates topic ideas inspired by subreddit discussions"""
    subreddits = [
        "RomanceBooks", "romantasy", "fantasyromance", "Fantasy",
        "fantasywriters", "RomanceAuthors", "YAwriters", "writing"
    ]

    prompt = f"""You are a content strategist for "Plot Brew," researching trending topics in the romantasy community.

Based on typical discussions in these subreddits: {', '.join(subreddits)}

Generate {count} writing advice topic ideas inspired by common debates, questions, and pain points you'd expect to find there.

**Guidelines:**
- Think about what writers ask about most
- Consider trending debates (love triangles, tropes, market saturation, etc.)
- Focus on practical craft questions
- Make them specific to romantasy

Return ONLY this JSON format:

{{
  "topics": [
    {{
      "topic": "Topic title",
      "description": "One sentence explaining what this covers",
      "category": "craft/tropes/market/structure/etc",
      "inspired_by": "Brief note about what subreddit discussion inspired this"
    }},
    ...
  ]
}}
"""

    response = anthropic_client.messages.create(
        model="claude-sonnet-4-5",
        max_tokens=1500,
        messages=[{"role": "user", "content": prompt}]
    )

    result = extract_json(response.content[0].text)
    return result.get("topics", [])

# ==================== PHASE 3: RESEARCH ====================

def run_web_search(query: str) -> str:
    """Run web search using GPT-4o-mini"""
    if not openai_client:
        raise Exception("OpenAI client not available for web search")

    response = openai_client.chat.completions.create(
        model="gpt-4o-mini",  # GPT-4o mini Search Preview
        messages=[{
            "role": "user",
            "content": f"""Search the web for: {query}

Find recent discussions, trends, and conversations about this topic in the romantasy/writing community.

Summarize the key findings, including:
- Main discussions or debates happening
- Common questions or pain points
- Trending opinions or hot takes
- Specific examples of what people are saying
- URLs or sources where relevant

Focus on actionable insights."""
        }]
    )

    return response.choices[0].message.content

# ==================== PHASE 4: POST DRAFTING ====================

def draft_social_posts(topic: str, platforms: List[str], research: Optional[str] = None) -> Dict[str, str]:
    """Generate platform-specific posts"""
    research_context = f"\n\n**RESEARCH CONTEXT:**\n{research}" if research else ""

    platform_specs = {
        "twitter": "280 chars max - Hook + craft insight + question",
        "threads": "500 chars max - Personal story + insights + community question",
        "pinterest": "500 chars - Educational, keyword-rich, list format",
        "instagram": "2200 chars max - Story-driven + 5-7 tips + hashtags"
    }

    specs = "\n".join([f"{p.upper()}: {platform_specs[p]}" for p in platforms])

    prompt = f"""You are creating social media posts for "Plot Brew," a romantasy writing advice platform.

**TOPIC:** {topic}{research_context}

**YOUR VOICE:**
- Personal and vulnerable (share writing journey)
- Celebratory of romantasy (treat it with intellectual respect)
- Community-focused ("we" language, not "you")
- Geeky enthusiasm about tropes and craft
- Relatable struggles of writing life

**PLATFORMS TO CREATE:**
{specs}

Return ONLY this JSON format:

{{
  {', '.join([f'"{p}": "Your {p} post here"' for p in platforms])}
}}
"""

    response = anthropic_client.messages.create(
        model="claude-sonnet-4-5",
        max_tokens=2500,
        messages=[{"role": "user", "content": prompt}]
    )

    return extract_json(response.content[0].text)

def revise_post(original_post: str, platform: str, feedback: str) -> str:
    """Revise a post based on user feedback"""
    prompt = f"""You are revising a social media post for Plot Brew.

**PLATFORM:** {platform} (limit: {PLATFORM_LIMITS[platform]} chars)

**ORIGINAL POST:**
{original_post}

**USER FEEDBACK:**
{feedback}

Apply the feedback and return ONLY the revised post (no JSON, no preamble).
"""

    response = anthropic_client.messages.create(
        model="claude-sonnet-4-5",
        max_tokens=1000,
        messages=[{"role": "user", "content": prompt}]
    )

    return response.content[0].text.strip()

# ==================== PHASE 5: IMAGE GENERATION ====================

def generate_image_prompt(topic: str, platform: str, feedback: Optional[str] = None) -> str:
    """Generate image prompt for Gemini"""
    aspect_ratios = {"twitter": "16:9", "threads": "16:9", "pinterest": "2:3", "instagram": "1:1"}
    aspect_ratio = aspect_ratios.get(platform, "1:1")

    feedback_context = f"\n\n**USER FEEDBACK ON PREVIOUS ATTEMPT:**\n{feedback}" if feedback else ""

    prompt = f"""Create a detailed image generation prompt for a social media graphic about romantasy writing advice.

**TOPIC:** {topic}
**PLATFORM:** {platform} (aspect ratio: {aspect_ratio}){feedback_context}

**BRAND: "Plot Brew"**
- Visual Style: Warm, magical, whimsical yet sophisticated
- Color Palette: Warm jewel tones (burgundy, forest green, gold) OR twilight colors (purple, rose gold, midnight blue)
- Typography: Mix of elegant serif for headlines and clean sans-serif
- Visual Elements: Starbursts, constellations, book spines, quill pens, botanical illustrations
- Mood: Warm, inviting, creative, slightly magical
- Branding: Include "PLOT BREW" text

**TEXT TO INCLUDE:** "{topic}"

Return ONLY the image generation prompt (start with "Create a...").
"""

    response = anthropic_client.messages.create(
        model="claude-sonnet-4-5",
        max_tokens=800,
        messages=[{"role": "user", "content": prompt}]
    )

    return response.content[0].text.strip()

def generate_image(image_prompt: str, platform: str, topic_slug: str) -> Optional[str]:
    """Generate image using Gemini"""
    if not GENAI_AVAILABLE or not GOOGLE_API_KEY:
        return None

    aspect_ratios = {"twitter": "16:9", "threads": "16:9", "pinterest": "2:3", "instagram": "1:1"}
    aspect_ratio = aspect_ratios.get(platform, "1:1")

    try:
        client = genai.Client(api_key=GOOGLE_API_KEY)
        response = client.models.generate_content(
            model="gemini-2.0-flash-exp",
            contents=[image_prompt],
            config=types.GenerateContentConfig(
                response_modalities=['Image'],
                image_config=types.ImageConfig(aspect_ratio=aspect_ratio)
            )
        )

        timestamp = datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')
        image_filename = f"batch_{topic_slug}_{platform}_{timestamp}.png"

        for part in response.parts:
            if part.inline_data is not None:
                image = part.as_image()
                image.save(image_filename)
                return image_filename

        return None
    except Exception as e:
        print(f"✗ Image generation failed: {e}")
        return None

# ==================== PHASE 6: POSTING ====================

def post_to_twitter(text: str, image_path: Optional[str] = None) -> bool:
    """Post to Twitter"""
    if not all([TWITTER_API_KEY, TWITTER_API_SECRET, TWITTER_ACCESS_TOKEN, TWITTER_ACCESS_SECRET]) or not TWEEPY_AVAILABLE:
        print("  ⚠️  Twitter not configured")
        return False

    try:
        client = tweepy.Client(
            consumer_key=TWITTER_API_KEY,
            consumer_secret=TWITTER_API_SECRET,
            access_token=TWITTER_ACCESS_TOKEN,
            access_token_secret=TWITTER_ACCESS_SECRET
        )

        media_id = None
        if image_path and os.path.exists(image_path):
            auth = tweepy.OAuth1UserHandler(
                TWITTER_API_KEY, TWITTER_API_SECRET,
                TWITTER_ACCESS_TOKEN, TWITTER_ACCESS_SECRET
            )
            api_v1 = tweepy.API(auth)
            media = api_v1.media_upload(filename=image_path)
            media_id = media.media_id

        if media_id:
            response = client.create_tweet(text=text, media_ids=[media_id])
        else:
            response = client.create_tweet(text=text)

        print(f"  ✓ Posted to Twitter")
        return True
    except Exception as e:
        print(f"  ✗ Twitter failed: {e}")
        return False

def post_to_threads(text: str, image_path: Optional[str] = None) -> bool:
    """Post to Threads"""
    if not all([META_ACCESS_TOKEN, META_USER_ID]):
        print("  ⚠️  Threads not configured")
        return False

    try:
        url = f"https://graph.threads.net/v1.0/{META_USER_ID}/threads"
        data = {
            "media_type": "TEXT",
            "text": text,
            "access_token": META_ACCESS_TOKEN
        }

        response = requests.post(url, json=data, timeout=30)
        response.raise_for_status()
        container_id = response.json()["id"]

        publish_url = f"https://graph.threads.net/v1.0/{META_USER_ID}/threads_publish"
        publish_data = {
            "creation_id": container_id,
            "access_token": META_ACCESS_TOKEN
        }

        publish_response = requests.post(publish_url, json=publish_data, timeout=30)
        publish_response.raise_for_status()

        print(f"  ✓ Posted to Threads")
        return True
    except Exception as e:
        print(f"  ✗ Threads failed: {e}")
        return False

def post_to_pinterest(text: str, image_path: Optional[str] = None) -> bool:
    """Post to Pinterest"""
    print("  ⚠️  Pinterest posting not fully implemented")
    return False

def email_instagram_post(text: str, image_path: Optional[str] = None) -> bool:
    """Email Instagram post"""
    if not all([EMAIL_FROM, EMAIL_TO, SMTP_USER, SMTP_PASSWORD]):
        print("  ⚠️  Email not configured")
        return False

    try:
        msg = MIMEMultipart()
        msg['From'] = EMAIL_FROM
        msg['To'] = EMAIL_TO
        msg['Subject'] = f"Plot Brew Instagram Post - {datetime.now().strftime('%Y-%m-%d')}"

        body = f"""Plot Brew Instagram Post Ready

CAPTION:
{text}

Image attached (if generated).
"""
        msg.attach(MIMEText(body, 'plain'))

        if image_path and os.path.exists(image_path):
            with open(image_path, 'rb') as f:
                img_data = f.read()
                image = MIMEImage(img_data, name=os.path.basename(image_path))
                msg.attach(image)

        with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as server:
            server.starttls()
            server.login(SMTP_USER, SMTP_PASSWORD)
            server.send_message(msg)

        print(f"  ✓ Instagram post emailed")
        return True
    except Exception as e:
        print(f"  ✗ Email failed: {e}")
        return False

# ==================== UTILITIES ====================

def extract_json(text: str) -> Dict:
    """Extract JSON from AI response"""
    import re

    if "```json" in text:
        text = text.split("```json")[1].split("```")[0].strip()
    elif "```" in text:
        text = text.split("```")[1].split("```")[0].strip()

    start = text.find("{")
    end = text.rfind("}") + 1
    if start != -1 and end > start:
        text = text[start:end]

    try:
        return json.loads(text)
    except:
        return {}

# ==================== MAIN WORKFLOW ====================

def main():
    print("="*80)
    print("ROMANTASY SOCIAL MEDIA AUTOMATION - BATCH WORKFLOW")
    print("Plot Brew - Multi-Topic Content Generation")
    print("="*80)

    # Check for saved sessions
    saved_sessions = list_saved_sessions()
    selected_topics = []
    start_phase = "brainstorm"

    if saved_sessions:
        print(f"\n💾 Found {len(saved_sessions)} saved session(s)")
        if confirm_action("Resume from a saved session?"):
            # Show sessions
            for i, (filename, data) in enumerate(saved_sessions[:5], 1):
                saved_at = data.get('saved_at', 'Unknown')
                phase = data.get('current_phase', 'Unknown')
                topic_count = len(data.get('selected_topics', []))
                print(f"  {i}. {saved_at[:19]} - Phase: {phase} - {topic_count} topics")

            choice = input("\nEnter session number to resume (or 'n' to start fresh): ").strip()
            if choice.isdigit() and 1 <= int(choice) <= len(saved_sessions):
                session_data = saved_sessions[int(choice) - 1][1]
                selected_topics = session_data.get('selected_topics', [])
                start_phase = session_data.get('current_phase', 'brainstorm')
                print(f"\n✅ Resumed session with {len(selected_topics)} topics at phase: {start_phase}")

    # Show performance insights if available
    insights = get_performance_insights()
    if insights.get('total_posts', 0) > 0:
        print(f"\n📊 PERFORMANCE INSIGHTS ({insights['total_posts']} posts tracked):")
        for platform, styles in insights.get('platform_style_preferences', {}).items():
            top_style = max(styles, key=styles.get)
            print(f"  {platform}: You prefer '{top_style}' style ({styles[top_style]} times)")

    # PHASE 1: BRAINSTORM TOPICS
    if start_phase == "brainstorm":
        print("\n" + "="*80)
        print("PHASE 1: TOPIC BRAINSTORMING")
        print("="*80)

    print("\n🧠 Brainstorming topics...")
    direct_topics = brainstorm_direct_topics(5)
    subreddit_topics = brainstorm_subreddit_topics(5)

    all_topics = []
    print("\n📝 DIRECT TOPICS (from AI knowledge):")
    for i, t in enumerate(direct_topics):
        idx = len(all_topics)
        all_topics.append({**t, "source": "direct"})
        print(f"  {idx+1}. {t['topic']}")
        print(f"     {t['description']} [{t.get('category', 'general')}]")

    print("\n🔥 SUBREDDIT-INSPIRED TOPICS:")
    for i, t in enumerate(subreddit_topics):
        idx = len(all_topics)
        all_topics.append({**t, "source": "subreddit"})
        print(f"  {idx+1}. {t['topic']}")
        print(f"     {t['description']} [{t.get('category', 'general')}]")
        if 'inspired_by' in t:
            print(f"     Inspired by: {t['inspired_by']}")

    # PHASE 2: SELECT TOPICS & PLATFORMS
    print("\n" + "="*80)
    print("PHASE 2: SELECT TOPICS & PLATFORMS")
    print("="*80)

    selected_indices = prompt_multi_select(
        "Which topics would you like to create posts for?",
        [t['topic'] for t in all_topics]
    )

    selected_topics = []
    for idx in selected_indices:
        topic_data = all_topics[idx].copy()

        print(f"\n📌 Selected: {topic_data['topic']}")
        platform_indices = prompt_multi_select(
            "Which platforms for this topic?",
            ["Twitter", "Threads", "Pinterest", "Instagram"]
        )

        platforms = [["twitter", "threads", "pinterest", "instagram"][i] for i in platform_indices]
        topic_data['platforms'] = platforms
        topic_data['research'] = None
        topic_data['posts'] = {}
        topic_data['images'] = {}

        selected_topics.append(topic_data)

    print(f"\n✅ Selected {len(selected_topics)} topics for content creation")

    # PHASE 3: RESEARCH (for each topic)
    print("\n" + "="*80)
    print("PHASE 3: RESEARCH")
    print("="*80)

    for i, topic_data in enumerate(selected_topics, 1):
        print(f"\n--- TOPIC {i}/{len(selected_topics)}: {topic_data['topic']} ---")

        research_choice = prompt_user(
            "How would you like to gather research?",
            [
                "AI generates search query and runs GPT-4o-mini search",
                "I'll provide my own research",
                "Skip research (AI will use general knowledge)"
            ]
        )

        if "AI generates" in research_choice:
            print("\n🔍 Generating search query...")
            query = f"romantasy writing {topic_data['topic']} discussions trends tips"
            print(f"🔎 Search query: {query}")

            if confirm_action("Run this search?"):
                print("🌐 Searching...")
                try:
                    research = run_web_search(query)
                    print(f"\n📊 Preview: {research[:300]}...")
                    topic_data['research'] = research
                except Exception as e:
                    print(f"✗ Search failed: {e}")

        elif "provide my own" in research_choice:
            research = get_multiline_input("Paste your research:")
            if research:
                topic_data['research'] = research
                print("✓ Research saved")

    # Save session after research
    if confirm_action("\n💾 Save session before continuing?"):
        session_file = save_session({'selected_topics': selected_topics}, 'post_drafting')
        print(f"✓ Session saved: {session_file}")

    # PHASE 4: DRAFT POSTS (with A/B testing & feedback loop)
    print("\n" + "="*80)
    print("PHASE 4: POST DRAFTING (A/B TESTING)")
    print("="*80)

    for i, topic_data in enumerate(selected_topics, 1):
        print(f"\n--- TOPIC {i}/{len(selected_topics)}: {topic_data['topic']} ---")
        topic_data['posts'] = {}
        topic_data['hashtags'] = {}

        # Generate posts for each platform
        for platform in topic_data['platforms']:
            satisfied = False

            while not satisfied:
                print(f"\n{platform.upper()}:")

                # A/B TESTING: Generate 3 variations
                print("🎨 Generating 3 variations for A/B testing...")
                variations = draft_post_variations(
                    topic_data['topic'],
                    platform,
                    topic_data.get('research'),
                    count=3
                )

                if not variations:
                    print("✗ Failed to generate variations")
                    if not confirm_action("Try again?"):
                        break
                    continue

                # Show all variations
                print("\n" + "─"*60)
                for j, var in enumerate(variations, 1):
                    style = var.get('style', 'unknown')
                    post_text = var.get('post', '')
                    print(f"\nVARIATION {j} - {style.upper()}")
                    print(post_text)
                    print(f"Characters: {len(post_text)}/{PLATFORM_LIMITS[platform]}")
                    print("─"*60)

                action = prompt_user(
                    f"What would you like to do?",
                    [
                        "Select variation 1",
                        "Select variation 2",
                        "Select variation 3",
                        "Give feedback and regenerate all",
                        "Skip this platform"
                    ]
                )

                if "Select variation" in action:
                    var_num = int(action.split()[-1]) - 1
                    selected_var = variations[var_num]
                    current_post = selected_var.get('post', '')

                    # Track selection for learning
                    track_post_performance(
                        topic_data['topic'],
                        platform,
                        selected_var.get('style', 'unknown'),
                        current_post
                    )

                    # Generate hashtags
                    print(f"\n🏷️  Generating hashtags for {platform}...")
                    hashtags_data = generate_hashtags(topic_data['topic'], platform)
                    recommended = hashtags_data.get('recommended', [])

                    print(f"\n📌 RECOMMENDED HASHTAGS ({len(recommended)}):")
                    print(" ".join(recommended))

                    if confirm_action("\nUse these hashtags?"):
                        topic_data['hashtags'][platform] = recommended
                        # Append to Instagram post if applicable
                        if platform == "instagram" and recommended:
                            current_post += "\n\n" + " ".join(recommended)

                    topic_data['posts'][platform] = current_post
                    satisfied = True

                elif "feedback" in action:
                    feedback = get_multiline_input("Enter your feedback:")
                    print("✏️  Regenerating with feedback...")
                    # This will loop and regenerate
                    continue

                else:  # Skip
                    if platform in topic_data['platforms']:
                        topic_data['platforms'].remove(platform)
                    satisfied = True

    # Save session after posts
    if confirm_action("\n💾 Save session before image generation?"):
        session_file = save_session({'selected_topics': selected_topics}, 'image_generation')
        print(f"✓ Session saved: {session_file}")

    # PHASE 5: IMAGE GENERATION (with feedback loop)
    print("\n" + "="*80)
    print("PHASE 5: IMAGE GENERATION")
    print("="*80)

    if not confirm_action("Generate images for posts?"):
        print("Skipping image generation")
    else:
        for i, topic_data in enumerate(selected_topics, 1):
            topic_slug = topic_data['topic'][:30].replace(" ", "_").lower()
            print(f"\n--- TOPIC {i}/{len(selected_topics)}: {topic_data['topic']} ---")

            for platform in topic_data['platforms']:
                if platform not in topic_data['posts']:
                    continue

                print(f"\n🎨 {platform.upper()} image:")
                satisfied = False
                image_feedback = None

                while not satisfied:
                    print("  Generating image prompt...")
                    prompt_text = generate_image_prompt(topic_data['topic'], platform, image_feedback)
                    print(f"\n  Prompt: {prompt_text[:200]}...")

                    if not confirm_action("  Generate image with this prompt?"):
                        action = prompt_user("What would you like to do?",
                                           ["Give feedback to improve prompt", "Skip image for this platform"])
                        if "feedback" in action:
                            image_feedback = get_multiline_input("  Enter feedback for image prompt:")
                            continue
                        else:
                            break

                    print("  🖼️  Generating image...")
                    image_path = generate_image(prompt_text, platform, topic_slug)

                    if image_path:
                        print(f"  ✓ Saved: {image_path}")

                        if confirm_action("  Accept this image?"):
                            topic_data['images'][platform] = image_path
                            satisfied = True
                        else:
                            image_feedback = get_multiline_input("  Enter feedback for next attempt:")
                    else:
                        print("  ✗ Generation failed")
                        if not confirm_action("  Try again?"):
                            break

    # PHASE 6: FINAL APPROVAL & POSTING
    print("\n" + "="*80)
    print("PHASE 6: FINAL APPROVAL & POSTING")
    print("="*80)

    print("\n📋 CONTENT SUMMARY:")
    for i, topic_data in enumerate(selected_topics, 1):
        print(f"\n{i}. {topic_data['topic']}")
        for platform in topic_data['platforms']:
            post = topic_data['posts'].get(platform, "")
            image = topic_data['images'].get(platform)
            hashtags = topic_data.get('hashtags', {}).get(platform, [])
            extras = []
            if image:
                extras.append("image")
            if hashtags:
                extras.append(f"{len(hashtags)} hashtags")
            extras_str = " + " + ", ".join(extras) if extras else ""
            print(f"   • {platform}: {len(post)} chars{extras_str}")

    if not confirm_action("\n✅ Ready to post?"):
        print("\n💾 Content saved. Exiting without posting.")
        return

    print("\n📤 POSTING...")
    for i, topic_data in enumerate(selected_topics, 1):
        print(f"\n--- TOPIC {i}: {topic_data['topic']} ---")

        for platform in topic_data['platforms']:
            post_text = topic_data['posts'].get(platform)
            image_path = topic_data['images'].get(platform)

            if not post_text:
                continue

            print(f"  {platform}:", end=" ")

            if platform == "twitter":
                post_to_twitter(post_text, image_path)
            elif platform == "threads":
                post_to_threads(post_text, image_path)
            elif platform == "pinterest":
                post_to_pinterest(post_text, image_path)
            elif platform == "instagram":
                email_instagram_post(post_text, image_path)

    # Save report
    timestamp = datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')
    report = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "topics": selected_topics
    }

    report_file = f"batch_report_{timestamp}.json"
    with open(report_file, 'w', encoding='utf-8') as f:
        json.dump(report, f, indent=2, ensure_ascii=False)

    print("\n" + "="*80)
    print(f"✅ Batch complete! Report: {report_file}")
    print("="*80)

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n⚠️  Session interrupted by user")
        sys.exit(0)
