#!/usr/bin/env python3
# automate_advertising_social_batch.py
# Batch social media automation for advertising/marketing content (Twitter + Threads)

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

TWITTER_API_KEY = os.getenv("TWITTER_API_KEY")
TWITTER_API_SECRET = os.getenv("TWITTER_API_SECRET")
TWITTER_ACCESS_TOKEN = os.getenv("TWITTER_ACCESS_TOKEN")
TWITTER_ACCESS_SECRET = os.getenv("TWITTER_ACCESS_SECRET")

META_ACCESS_TOKEN = os.getenv("META_ACCESS_TOKEN")
META_USER_ID = os.getenv("META_USER_ID")

if not ANTHROPIC_API_KEY:
    print("ERROR: ANTHROPIC_API_KEY not configured")
    sys.exit(1)

anthropic_client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
openai_client = None
if OPENAI_AVAILABLE and OPENAI_API_KEY:
    openai_client = OpenAI(api_key=OPENAI_API_KEY)

PLATFORM_LIMITS = {
    "twitter": 280,
    "threads": 500
}

# Session management
SESSION_DIR = "advertising_social_sessions"
PERFORMANCE_DB = "advertising_post_performance.json"

# Blog context
BLOG_THESIS = "An Auditor's, Agency Investment Manager's, and In-House Analyst's View on Advertising Investment & Accountability."

EXPERT_PERSONA = """Melissa - a senior analyst with 5+ years across:
1. Media Auditor (external auditor checking ad spend/quality across all channels)
2. Agency Investment Manager (managing global ad investments at holding company)
3. In-House Analyst (building automation/dashboards for advertising analytics)

Voice: First-person, anonymous, data-driven, challenging conventional wisdom"""

PILLARS = {
    "accountability": "Media Accountability & Performance (Auditor lens) - ad quality, waste, fraud, measurement",
    "investment": "Advertising Strategy & Investment (Agency Manager lens) - client risk, cost analysis, media buying",
    "analytics": "Advertising Analytics & Automation (In-House lens) - Python/SQL, dashboards, data pipelines"
}

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
    """Multi-select prompt"""
    print(f"\n{message}")
    for i, option in enumerate(options, 1):
        print(f"  {i}. {option}")

    print("\nEnter numbers separated by commas (e.g., 1,2) or 'all':")
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
    """Get multi-line text input"""
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

def extract_json(text: str) -> Dict:
    """Extract JSON from AI response"""
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

# ==================== SESSION MANAGEMENT ====================

def save_session(session_data: Dict, phase: str) -> str:
    """Save current session"""
    if not os.path.exists(SESSION_DIR):
        os.makedirs(SESSION_DIR)

    timestamp = datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')
    filename = f"{SESSION_DIR}/session_{timestamp}.json"

    session_data['current_phase'] = phase
    session_data['saved_at'] = datetime.now(timezone.utc).isoformat()

    with open(filename, 'w', encoding='utf-8') as f:
        json.dump(session_data, f, indent=2, ensure_ascii=False)

    return filename

def list_saved_sessions() -> List[Tuple[str, Dict]]:
    """List all saved sessions"""
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

# ==================== PERFORMANCE TRACKING ====================

def track_post_performance(topic: str, platform: str, variation_style: str, post_text: str):
    """Track which variations get selected"""
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
    """Analyze historical performance"""
    if not os.path.exists(PERFORMANCE_DB):
        return {"message": "No performance data yet"}

    with open(PERFORMANCE_DB, 'r') as f:
        data = json.load(f)

    selections = data.get("selections", [])
    if not selections:
        return {"message": "No selections tracked yet"}

    platform_styles = {}
    for sel in selections:
        platform = sel['platform']
        style = sel['variation_style']

        if platform not in platform_styles:
            platform_styles[platform] = {}

        platform_styles[platform][style] = platform_styles[platform].get(style, 0) + 1

    return {
        "total_posts": len(selections),
        "platform_style_preferences": platform_styles
    }

# ==================== CONTENT GENERATION ====================

def brainstorm_direct_topics(count: int = 5) -> List[Dict[str, str]]:
    """AI brainstorms advertising topics"""
    prompt = f"""You are a content strategist for an advertising/marketing insights blog.

{EXPERT_PERSONA}

Blog thesis: {BLOG_THESIS}

Brainstorm {count} specific, actionable topics for Twitter/Threads that would resonate with marketing professionals, media buyers, ad tech folks, and CMOs.

**Topic Guidelines:**
- Specific to paid advertising, media buying, ad tech, or advertising analytics
- Insider perspective that challenges conventional wisdom
- Data-driven or based on real industry experience
- Sparks professional discussion
- Mix across the three pillars: {', '.join(PILLARS.keys())}

**Good Topics:**
- "Why Most Attribution Models are Measuring the Wrong Thing"
- "The Hidden Cost of Poor Media Planning (From 100+ Audits)"
- "How I Automated Cross-Platform Campaign Reporting in Python"
- "Meta's Latest API Changes: What They're Not Telling Agencies"

Return ONLY this JSON format:

{{
  "topics": [
    {{
      "topic": "Topic title",
      "description": "One sentence explaining the angle",
      "pillar": "accountability/investment/analytics"
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

def brainstorm_research_topics(count: int = 5) -> List[Dict[str, str]]:
    """AI generates topics based on industry discussions"""
    prompt = f"""You are researching trending topics in advertising/marketing communities.

Based on typical discussions in r/adops, r/advertising, r/marketing, LinkedIn marketing groups, and Twitter #AdTech conversations:

Generate {count} topic ideas inspired by current debates, platform changes, or pain points.

**Guidelines:**
- Based on real industry controversies or changes
- Insider analysis angle (auditor/agency manager/analyst perspective)
- Professional/data-driven approach
- Sparks debate among marketers

Return ONLY this JSON format:

{{
  "topics": [
    {{
      "topic": "Topic title",
      "description": "What makes this timely/controversial",
      "pillar": "accountability/investment/analytics",
      "inspired_by": "Brief note on industry discussion"
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

def run_web_search(query: str) -> str:
    """Run web search for ad tech/marketing topics"""
    if not openai_client:
        raise Exception("OpenAI client not available")

    response = openai_client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{
            "role": "user",
            "content": f"""Search for: {query}

Find recent discussions, news, or controversies in advertising/marketing.

Focus on:
- Platform changes (Meta, Google, TikTok, etc.)
- Ad tech news and debates
- Agency/client dynamics
- Measurement and attribution controversies
- Industry reports or data

Provide actionable insights for content."""
        }]
    )

    return response.choices[0].message.content

def draft_post_variations(topic: str, platform: str, research: Optional[str] = None, count: int = 3) -> List[Dict]:
    """Generate A/B test variations for advertising content"""

    research_context = f"\n\n**RESEARCH CONTEXT:**\n{research}" if research else ""

    platform_specs = {
        "twitter": "280 chars max - Hook + insight/data + question",
        "threads": "500 chars max - Mini case study or data breakdown + takeaway"
    }

    prompt = f"""Create {count} different variations of a social media post for an advertising insights account.

{EXPERT_PERSONA}

**TOPIC:** {topic}{research_context}
**PLATFORM:** {platform} - {platform_specs.get(platform, "")}

**YOUR VOICE ("Melissa"):**
- First-person but anonymous ("In my experience auditing..." "When I managed...")
- Data-driven and analytical
- Challenges conventional wisdom
- Professional but not corporate
- Insider perspective
- Slightly provocative/thought-provoking

**CREATE {count} VARIATIONS with different approaches:**

1. **Data/Audit Perspective** - Lead with numbers, findings, or audit insights
2. **Contrarian/Hot Take** - Challenge industry assumptions or platform claims
3. **Insider Story** - Personal anecdote from auditor/agency/analyst experience

**Each variation MUST:**
- Hook immediately (first sentence matters)
- Include credibility signal ("audited 100+ campaigns", "managed $X spend")
- End with engagement prompt (question, debate, or call-out)

Return ONLY this JSON format:

{{
  "variations": [
    {{
      "style": "data",
      "post": "Your post text here"
    }},
    {{
      "style": "contrarian",
      "post": "Your post text here"
    }},
    {{
      "style": "insider",
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

def create_twitter_thread(topic: str, research: Optional[str] = None, depth: str = "medium") -> List[str]:
    """Create Twitter thread for advertising topics"""

    research_context = f"\n\n**RESEARCH CONTEXT:**\n{research}" if research else ""

    tweet_counts = {"short": 5, "medium": 7, "long": 10}
    count = tweet_counts.get(depth, 7)

    prompt = f"""Create a Twitter thread for an advertising insights account.

{EXPERT_PERSONA}

**TOPIC:** {topic}{research_context}
**THREAD LENGTH:** {count} tweets

**VOICE:**
- Data-driven, insider perspective
- First-person anonymous ("In my audit work..." "When I analyzed...")
- Challenges conventional wisdom
- Professional but engaging

**THREAD STRUCTURE:**
1. Hook tweet - Bold claim or surprising data point
2-{count-2}. Value tweets - Insights, data, examples from experience
{count-1}. Depth tweet - The "why this matters" insight
{count}. CTA tweet - Discussion prompt or debate question

**Each tweet MUST:**
- Under 280 characters
- Include credibility signals when relevant
- Flow together as a cohesive narrative
- Use data/numbers when possible

Return ONLY this JSON format:

{{
  "tweets": ["Tweet 1", "Tweet 2", ...]
}}
"""

    response = anthropic_client.messages.create(
        model="claude-sonnet-4-5",
        max_tokens=2500,
        messages=[{"role": "user", "content": prompt}]
    )

    result = extract_json(response.content[0].text)
    return result.get('tweets', [])

def generate_hashtags(topic: str, platform: str) -> Dict[str, List[str]]:
    """Generate hashtags for advertising/marketing content"""

    platform_guidelines = {
        "twitter": "1-3 strategic hashtags. Professional/industry-specific.",
        "threads": "2-3 hashtags. Focus on marketing community tags."
    }

    prompt = f"""Generate strategic hashtags for advertising/marketing content.

**TOPIC:** {topic}
**PLATFORM:** {platform}
**GUIDELINES:** {platform_guidelines.get(platform, "")}

**Hashtag Strategy:**
- INDUSTRY tags (#AdTech, #MarketingOps, #MediaBuying, #AdOps)
- TOPIC tags (#Attribution, #Programmatic, #Analytics, #MediaPlanning)
- PROFESSIONAL tags (#B2BMarketing, #Marketing, #Advertising)

**Avoid:**
- Generic hashtags (#Marketing101, #DigitalMarketing)
- Consumer-facing tags
- Overly broad tags

Return ONLY this JSON format:

{{
  "recommended": ["#tag1", "#tag2", "#tag3"]
}}
"""

    response = anthropic_client.messages.create(
        model="claude-sonnet-4-5",
        max_tokens=500,
        messages=[{"role": "user", "content": prompt}]
    )

    return extract_json(response.content[0].text)

def generate_cta_options(topic: str) -> List[Dict]:
    """Generate CTA variations for professional audience"""

    prompt = f"""Generate 5 different CTAs for an advertising/marketing post.

**TOPIC:** {topic}

**CTA TYPES:**
1. Debate starter - Pose controversial question
2. Experience share - Ask for others' data/experience
3. Poll/Quick response - Simple agree/disagree or multiple choice
4. Resource request - "What tools do you use for this?"
5. Challenge - "Prove me wrong" or "Change my mind"

**Audience:** Marketing professionals, media buyers, ad tech folks, CMOs

Return ONLY this JSON format:

{{
  "ctas": [
    {{
      "type": "debate",
      "text": "Your CTA text",
      "purpose": "Why this works"
    }},
    ...
  ]
}}
"""

    response = anthropic_client.messages.create(
        model="claude-sonnet-4-5",
        max_tokens=800,
        messages=[{"role": "user", "content": prompt}]
    )

    result = extract_json(response.content[0].text)
    return result.get('ctas', [])

def optimize_emoji_placement(post: str, platform: str) -> str:
    """Add strategic emojis (lighter for professional audience)"""

    prompt = f"""Add strategic emojis to this professional marketing post.

**PLATFORM:** {platform}
**EMOJI LEVEL:** light (1-2 emojis max - keep it professional)

**POST:**
{post}

**GUIDELINES:**
- Very sparingly - this is B2B/professional
- Use relevant emojis: 📊 📈 💰 🎯 ⚠️ 💡 📉 🔍
- Place strategically (not at random)
- When in doubt, use fewer

Return ONLY the post with emojis (no explanation).
"""

    response = anthropic_client.messages.create(
        model="claude-sonnet-4-5",
        max_tokens=800,
        messages=[{"role": "user", "content": prompt}]
    )

    return response.content[0].text.strip()

def analyze_content_balance(topics: List[Dict]) -> Dict:
    """Check balance across advertising pillars"""

    pillar_counts = {}
    for topic in topics:
        pillar = topic.get('pillar', 'general')
        pillar_counts[pillar] = pillar_counts.get(pillar, 0) + 1

    total = len(topics)

    balance = {}
    for pillar, count in pillar_counts.items():
        balance[pillar] = {
            "count": count,
            "percentage": (count / total * 100) if total > 0 else 0
        }

    warnings = []
    if any(b['percentage'] > 60 for b in balance.values()):
        dominant = max(balance.items(), key=lambda x: x[1]['percentage'])
        warnings.append(f"Over-indexed on {dominant[0]} ({dominant[1]['percentage']:.0f}%)")

    missing = set(['accountability', 'investment', 'analytics']) - set(balance.keys())
    if missing:
        warnings.append(f"Missing pillars: {', '.join(missing)}")

    return {
        "balance": balance,
        "warnings": warnings,
        "total_topics": total
    }

def suggest_posting_schedule(topics: List[Dict], days: int = 7) -> List[Dict]:
    """Create posting schedule"""

    # Best times for B2B marketing audience (EST)
    optimal_times = {
        "twitter": [(9, 0), (12, 0), (14, 0), (16, 0)],  # Business hours
        "threads": [(10, 0), (13, 0), (15, 0)]  # Mid-morning, lunch, mid-afternoon
    }

    day_names = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]

    schedule = []
    current_day = 0

    for topic in topics:
        for platform in topic.get('platforms', []):
            if platform not in topic.get('posts', {}):
                continue

            times = optimal_times.get(platform, [(12, 0)])
            time_idx = len([s for s in schedule if s['platform'] == platform]) % len(times)
            hour, minute = times[time_idx]

            # Skip weekends for B2B content unless specified
            day_num = current_day % days
            if day_num >= 5:  # Saturday/Sunday
                current_day += 1
                day_num = current_day % days

            day = day_names[day_num]

            schedule.append({
                "day": day,
                "day_num": day_num,
                "time": f"{hour:02d}:{minute:02d}",
                "hour": hour,
                "platform": platform,
                "topic": topic['topic'],
                "post": topic['posts'][platform]
            })

            current_day += 1

    schedule.sort(key=lambda x: (x['day_num'], x['hour']))
    return schedule

def export_schedule_csv(schedule: List[Dict], filename: str = None) -> str:
    """Export schedule to CSV"""
    import csv

    if not filename:
        timestamp = datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')
        filename = f"advertising_schedule_{timestamp}.csv"

    with open(filename, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=[
            'day', 'time', 'platform', 'topic', 'post_preview'
        ])
        writer.writeheader()

        for item in schedule:
            writer.writerow({
                'day': item['day'],
                'time': item['time'],
                'platform': item['platform'],
                'topic': item['topic'],
                'post_preview': item['post'][:100] + '...'
            })

    return filename

def repurpose_content(original_post: str, from_platform: str, to_platform: str, topic: str) -> str:
    """Repurpose advertising content across formats"""

    platform_specs = {
        "linkedin": "1000-1500 words - Professional article with data/examples",
        "newsletter": "800-1200 words - Deep dive with industry insights",
        "blog_outline": "Blog post structure with sections and key points"
    }

    prompt = f"""Repurpose this advertising/marketing content.

{EXPERT_PERSONA}

**ORIGINAL POST ({from_platform}):**
{original_post}

**TOPIC:** {topic}

**REPURPOSE TO:** {to_platform}
**TARGET FORMAT:** {platform_specs.get(to_platform, "Standard format")}

**GUIDELINES:**
- Keep the insider perspective and data-driven approach
- Expand with more detail/examples for longer formats
- Maintain first-person anonymous voice
- Add credibility signals from experience

Return ONLY the repurposed content.
"""

    response = anthropic_client.messages.create(
        model="claude-sonnet-4-5",
        max_tokens=2500,
        messages=[{"role": "user", "content": prompt}]
    )

    return response.content[0].text.strip()

# ==================== POSTING FUNCTIONS ====================

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

# ==================== IMAGE GENERATION ====================

def generate_image(topic: str, post_text: str, platform: str) -> Optional[str]:
    """Generate image for advertising content"""
    if not GENAI_AVAILABLE or not GOOGLE_API_KEY:
        print("  ⚠️  Image generation not available (google-genai not installed)")
        return None

    try:
        client = genai.Client(api_key=GOOGLE_API_KEY)

        # Professional B2B image prompts - data viz, charts, clean designs
        prompt = f"""Create a professional B2B marketing visual for this topic:

Topic: {topic}
Post: {post_text}

Style: Clean, professional, data-driven
Elements: Charts, graphs, or minimalist iconography
Colors: Professional palette (blues, grays, subtle accents)
Text: Minimal or none (post text will be in caption)

This is for advertising/marketing professionals - keep it polished and business-appropriate."""

        response = client.models.generate_image(
            model='gemini-2.0-flash-exp',
            prompt=prompt,
            config=types.GenerateImageConfig(
                number_of_images=1,
                aspect_ratio="1:1",
                safety_filter_level="block_some"
            )
        )

        if response.generated_images:
            timestamp = datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')
            platform_safe = platform.replace("/", "_")
            filename = f"advertising_image_{platform_safe}_{timestamp}.png"

            with open(filename, 'wb') as f:
                f.write(response.generated_images[0].image.data)

            print(f"  ✓ Image saved: {filename}")
            return filename

    except Exception as e:
        print(f"  ✗ Image generation failed: {e}")
        return None

# ==================== MAIN WORKFLOW ====================

def main():
    """Main batch workflow for advertising social media content"""

    print("=" * 60)
    print("  ADVERTISING SOCIAL MEDIA BATCH AUTOMATION")
    print("  Twitter + Threads for Marketing Professionals")
    print("=" * 60)

    # Check for saved sessions
    saved_sessions = list_saved_sessions()
    session_data = {}

    if saved_sessions:
        print(f"\n📁 Found {len(saved_sessions)} saved session(s)")
        if confirm_action("Resume a previous session?"):
            print("\nSaved sessions:")
            for i, (filename, data) in enumerate(saved_sessions[:5], 1):
                saved_at = data.get('saved_at', 'Unknown')
                phase = data.get('current_phase', 'Unknown')
                topic_count = len(data.get('selected_topics', []))
                print(f"  {i}. {saved_at[:19]} - Phase: {phase} - {topic_count} topics")

            choice = input("\nEnter session number (or 'n' for new): ").strip()
            if choice.isdigit() and 1 <= int(choice) <= len(saved_sessions):
                filename, session_data = saved_sessions[int(choice) - 1]
                print(f"✓ Resuming session from: {session_data.get('current_phase', 'Unknown')}")

    # ==================== PHASE 1: BRAINSTORM TOPICS ====================

    if 'all_topics' not in session_data:
        print("\n" + "=" * 60)
        print("PHASE 1: TOPIC BRAINSTORMING")
        print("=" * 60)

        print("\n🤖 AI is brainstorming 5 direct advertising topics...")
        direct_topics = brainstorm_direct_topics(count=5)

        print("\n🔍 AI is brainstorming 5 research-inspired topics...")
        research_topics = brainstorm_research_topics(count=5)

        all_topics = direct_topics + research_topics
        session_data['all_topics'] = all_topics

        print(f"\n✓ Generated {len(all_topics)} topic ideas")

        # Save session
        save_session(session_data, "brainstorming_complete")

    # ==================== PHASE 2: SELECT TOPICS & PLATFORMS ====================

    if 'selected_topics' not in session_data:
        print("\n" + "=" * 60)
        print("PHASE 2: SELECT TOPICS & PLATFORMS")
        print("=" * 60)

        all_topics = session_data['all_topics']

        print("\n📋 Available topics:")
        topic_options = []
        for i, topic in enumerate(all_topics, 1):
            desc = topic.get('description', '')
            pillar = topic.get('pillar', 'general')
            inspired = topic.get('inspired_by', '')
            marker = "🔍" if inspired else "💡"

            print(f"\n  {i}. {marker} {topic['topic']}")
            print(f"     Pillar: {pillar}")
            if desc:
                print(f"     {desc}")
            if inspired:
                print(f"     Inspired by: {inspired}")

            topic_options.append(topic['topic'])

        # Select topics
        selected_indices = prompt_multi_select(
            "Select which topics to create content for:",
            topic_options
        )

        selected_topics = [all_topics[i] for i in selected_indices]

        # For each topic, select platforms
        platforms_available = ["twitter", "threads"]

        for topic in selected_topics:
            print(f"\n📱 Platforms for: {topic['topic']}")
            platform_indices = prompt_multi_select(
                "Select platforms:",
                platforms_available
            )
            topic['platforms'] = [platforms_available[i] for i in platform_indices]

        session_data['selected_topics'] = selected_topics
        print(f"\n✓ Selected {len(selected_topics)} topics")

        # Save session
        save_session(session_data, "topics_selected")

    # ==================== PHASE 3: CONTENT BALANCE CHECK ====================

    if 'balance_checked' not in session_data:
        print("\n" + "=" * 60)
        print("PHASE 3: CONTENT BALANCE ANALYSIS")
        print("=" * 60)

        balance = analyze_content_balance(session_data['selected_topics'])

        print("\n📊 Content Balance:")
        for pillar, data in balance['balance'].items():
            print(f"  {pillar}: {data['count']} topics ({data['percentage']:.0f}%)")

        if balance['warnings']:
            print("\n⚠️  Warnings:")
            for warning in balance['warnings']:
                print(f"  - {warning}")
        else:
            print("\n✓ Good balance across pillars!")

        session_data['balance_checked'] = True
        save_session(session_data, "balance_checked")

    # ==================== PHASE 4: RESEARCH ====================

    if 'research_data' not in session_data:
        session_data['research_data'] = {}

    for topic in session_data['selected_topics']:
        topic_key = topic['topic']

        if topic_key in session_data['research_data']:
            continue

        print("\n" + "=" * 60)
        print(f"PHASE 4: RESEARCH - {topic['topic']}")
        print("=" * 60)

        research_choice = prompt_user(
            "How do you want to research this topic?",
            [
                "AI generates search query and runs research",
                "I'll provide my own research report",
                "Skip research (AI drafts without research)"
            ]
        )

        research_report = None

        if "AI generates" in research_choice:
            if openai_client:
                print("\n🔍 AI is generating a search query...")

                search_query = f"{topic['topic']} advertising marketing trends news discussions"
                print(f"   Query: {search_query}")

                print("\n🌐 Running web search...")
                try:
                    research_report = run_web_search(search_query)
                    print(f"\n✓ Research complete ({len(research_report)} chars)")
                    print(f"\nPreview: {research_report[:200]}...")

                    if not confirm_action("Accept this research?"):
                        research_report = None
                except Exception as e:
                    print(f"✗ Search failed: {e}")

            else:
                print("⚠️  OpenAI not available for web search")

        elif "provide my own" in research_choice:
            research_report = get_multiline_input(
                "Paste your research report below:"
            )
            print(f"\n✓ Received {len(research_report)} characters of research")

        session_data['research_data'][topic_key] = research_report
        save_session(session_data, f"research_{topic_key}")

    # ==================== PHASE 5: DRAFT POSTS ====================

    if 'posts' not in session_data:
        session_data['posts'] = {}

    for topic in session_data['selected_topics']:
        topic_key = topic['topic']

        if topic_key in session_data['posts']:
            continue

        print("\n" + "=" * 60)
        print(f"PHASE 5: DRAFTING - {topic['topic']}")
        print("=" * 60)

        topic['posts'] = {}
        research = session_data['research_data'].get(topic_key)

        for platform in topic['platforms']:
            print(f"\n📱 Creating content for {platform}...")

            # Check if this topic needs a thread
            if platform == "twitter":
                wants_thread = confirm_action("Create a Twitter thread instead of single tweet?")

                if wants_thread:
                    depth = prompt_user(
                        "Thread depth?",
                        ["short (5 tweets)", "medium (7 tweets)", "long (10 tweets)"]
                    )
                    depth_key = depth.split()[0]  # "short", "medium", or "long"

                    print(f"\n✍️  Generating {depth_key} thread...")
                    thread_tweets = create_twitter_thread(topic['topic'], research, depth_key)

                    print("\n📝 Thread preview:")
                    for i, tweet in enumerate(thread_tweets, 1):
                        print(f"\n  Tweet {i}/{len(thread_tweets)}:")
                        print(f"  {tweet}")
                        print(f"  ({len(tweet)} chars)")

                    if confirm_action("Use this thread?"):
                        topic['posts'][platform] = "\n\n".join(thread_tweets)
                        topic['is_thread'] = True
                        track_post_performance(topic['topic'], platform, "thread", topic['posts'][platform])
                        continue

            # Regular A/B testing for single posts
            print(f"\n✍️  Generating 3 variations...")
            variations = draft_post_variations(topic['topic'], platform, research, count=3)

            print(f"\n📝 Choose your variation for {platform}:")
            for i, var in enumerate(variations, 1):
                style = var.get('style', 'unknown')
                post = var.get('post', '')
                print(f"\n  {i}. [{style.upper()}]")
                print(f"     {post}")
                print(f"     ({len(post)} chars)")

            choice = prompt_user("Select variation:", [
                f"Variation 1 ({variations[0].get('style', '')})",
                f"Variation 2 ({variations[1].get('style', '')})",
                f"Variation 3 ({variations[2].get('style', '')})",
                "Regenerate all variations",
                "Skip this platform"
            ])

            if "Skip" in choice:
                continue

            if "Regenerate" in choice:
                print("\n🔄 Regenerating...")
                continue

            var_idx = int(choice.split()[1]) - 1
            selected = variations[var_idx]
            topic['posts'][platform] = selected['post']

            # Track performance
            track_post_performance(topic['topic'], platform, selected['style'], selected['post'])

        session_data['posts'][topic_key] = topic['posts']
        save_session(session_data, f"posts_{topic_key}")

    # ==================== PHASE 6: HASHTAGS, CTAs, EMOJIS ====================

    if 'enhancements' not in session_data:
        session_data['enhancements'] = {}

    for topic in session_data['selected_topics']:
        topic_key = topic['topic']

        if topic_key in session_data['enhancements']:
            continue

        print("\n" + "=" * 60)
        print(f"PHASE 6: ENHANCEMENTS - {topic['topic']}")
        print("=" * 60)

        topic['enhancements'] = {}

        # Hashtags for each platform
        for platform in topic['platforms']:
            if platform not in topic.get('posts', {}):
                continue

            print(f"\n🏷️  Generating hashtags for {platform}...")
            hashtag_result = generate_hashtags(topic['topic'], platform)

            recommended = hashtag_result.get('recommended', [])
            print(f"   Recommended: {' '.join(recommended)}")

            if confirm_action("Add these hashtags to the post?"):
                current_post = topic['posts'][platform]
                topic['posts'][platform] = f"{current_post}\n\n{' '.join(recommended)}"

        # CTA options
        print(f"\n💬 Generating CTA options...")
        cta_options = generate_cta_options(topic['topic'])

        print("\n📣 CTA Variations:")
        for i, cta in enumerate(cta_options[:3], 1):
            print(f"\n  {i}. [{cta.get('type', '')}]")
            print(f"     {cta.get('text', '')}")
            print(f"     Why: {cta.get('purpose', '')}")

        if confirm_action("Replace current CTAs with one of these?"):
            choice = prompt_user("Select CTA:", [
                f"CTA 1 ({cta_options[0].get('type', '')})",
                f"CTA 2 ({cta_options[1].get('type', '')})",
                f"CTA 3 ({cta_options[2].get('type', '')})",
                "Keep original CTAs"
            ])

            if "CTA" in choice:
                cta_idx = int(choice.split()[1]) - 1
                selected_cta = cta_options[cta_idx]['text']

                for platform in topic['platforms']:
                    if platform in topic.get('posts', {}):
                        # Replace the last sentence (likely the CTA)
                        current_post = topic['posts'][platform]
                        sentences = current_post.split('. ')
                        if len(sentences) > 1:
                            sentences[-1] = selected_cta
                            topic['posts'][platform] = '. '.join(sentences)

        # Emoji optimization
        for platform in topic['platforms']:
            if platform not in topic.get('posts', {}):
                continue

            print(f"\n😊 Optimize emoji placement for {platform}?")
            if confirm_action("Add strategic emojis?"):
                optimized = optimize_emoji_placement(topic['posts'][platform], platform)

                print(f"\n  Original: {topic['posts'][platform]}")
                print(f"\n  Optimized: {optimized}")

                if confirm_action("Use optimized version?"):
                    topic['posts'][platform] = optimized

        session_data['enhancements'][topic_key] = topic.get('enhancements', {})
        save_session(session_data, f"enhancements_{topic_key}")

    # ==================== PHASE 7: REPURPOSING (OPTIONAL) ====================

    if confirm_action("\n📄 Repurpose any content for other formats? (LinkedIn, newsletter, blog)"):
        print("\n" + "=" * 60)
        print("PHASE 7: CONTENT REPURPOSING")
        print("=" * 60)

        if 'repurposed' not in session_data:
            session_data['repurposed'] = {}

        for topic in session_data['selected_topics']:
            topic_key = topic['topic']

            if not topic.get('posts'):
                continue

            print(f"\n📄 Repurpose: {topic['topic']}")

            # Get primary platform post
            primary_platform = topic['platforms'][0] if topic['platforms'] else 'twitter'
            primary_post = topic['posts'].get(primary_platform, '')

            if not primary_post:
                continue

            repurpose_options = ["linkedin", "newsletter", "blog_outline"]

            selected = prompt_multi_select(
                "Repurpose to which formats?",
                repurpose_options + ["Skip"]
            )

            for idx in selected:
                if idx >= len(repurpose_options):
                    continue

                target_format = repurpose_options[idx]

                print(f"\n🔄 Repurposing to {target_format}...")
                repurposed = repurpose_content(
                    primary_post,
                    primary_platform,
                    target_format,
                    topic['topic']
                )

                print(f"\n✓ {target_format.upper()}:")
                print(repurposed[:500])
                if len(repurposed) > 500:
                    print("... (truncated)")

                if topic_key not in session_data['repurposed']:
                    session_data['repurposed'][topic_key] = {}

                session_data['repurposed'][topic_key][target_format] = repurposed

        save_session(session_data, "repurposing_complete")

    # ==================== PHASE 8: IMAGE GENERATION (OPTIONAL) ====================

    if confirm_action("\n🎨 Generate images for any posts?"):
        print("\n" + "=" * 60)
        print("PHASE 8: IMAGE GENERATION")
        print("=" * 60)

        if 'images' not in session_data:
            session_data['images'] = {}

        for topic in session_data['selected_topics']:
            topic_key = topic['topic']

            for platform in topic['platforms']:
                if platform not in topic.get('posts', {}):
                    continue

                print(f"\n🎨 Generate image for {platform} - {topic['topic']}?")
                if confirm_action("Generate?"):
                    image_path = generate_image(
                        topic['topic'],
                        topic['posts'][platform],
                        platform
                    )

                    if image_path:
                        if topic_key not in session_data['images']:
                            session_data['images'][topic_key] = {}
                        session_data['images'][topic_key][platform] = image_path

        save_session(session_data, "images_complete")

    # ==================== PHASE 9: CONTENT CALENDAR ====================

    print("\n" + "=" * 60)
    print("PHASE 9: CONTENT CALENDAR")
    print("=" * 60)

    days = 7  # Default to 1 week
    if confirm_action("\n📅 Create posting schedule?"):
        days_input = input("How many days to schedule over? (default 7): ").strip()
        if days_input.isdigit():
            days = int(days_input)

        schedule = suggest_posting_schedule(session_data['selected_topics'], days)

        print(f"\n📅 Suggested Schedule ({days} days, weekdays only):\n")
        current_day = None
        for item in schedule:
            if item['day'] != current_day:
                current_day = item['day']
                print(f"\n{current_day}:")

            print(f"  {item['time']} - {item['platform']}: {item['topic']}")

        # Export to CSV
        if confirm_action("\n💾 Export schedule to CSV?"):
            csv_file = export_schedule_csv(schedule)
            print(f"✓ Exported to: {csv_file}")

        session_data['schedule'] = schedule

    # ==================== PHASE 10: BATCH POSTING ====================

    print("\n" + "=" * 60)
    print("PHASE 10: BATCH POSTING")
    print("=" * 60)

    print("\n📊 Summary:")
    print(f"  Topics: {len(session_data['selected_topics'])}")
    total_posts = sum(len(t.get('posts', {})) for t in session_data['selected_topics'])
    print(f"  Total posts: {total_posts}")

    if not confirm_action("\n🚀 Ready to post everything?"):
        print("\n💾 Session saved. Run again to resume.")
        save_session(session_data, "ready_to_post")
        return

    print("\n🚀 Posting...")

    posted_count = 0
    failed_count = 0

    for topic in session_data['selected_topics']:
        topic_key = topic['topic']

        print(f"\n📤 Posting: {topic['topic']}")

        for platform in topic['platforms']:
            if platform not in topic.get('posts', {}):
                continue

            post_text = topic['posts'][platform]
            image_path = session_data.get('images', {}).get(topic_key, {}).get(platform)

            print(f"\n  {platform}:")
            print(f"  {post_text[:100]}...")

            success = False

            if platform == "twitter":
                success = post_to_twitter(post_text, image_path)
            elif platform == "threads":
                success = post_to_threads(post_text, image_path)

            if success:
                posted_count += 1
            else:
                failed_count += 1

    # ==================== COMPLETION ====================

    print("\n" + "=" * 60)
    print("✅ BATCH POSTING COMPLETE")
    print("=" * 60)

    print(f"\n📊 Results:")
    print(f"  ✓ Posted: {posted_count}")
    print(f"  ✗ Failed: {failed_count}")

    # Show performance insights
    insights = get_performance_insights()
    if insights.get('total_posts', 0) > 0:
        print(f"\n📈 Historical Performance:")
        print(f"  Total posts tracked: {insights['total_posts']}")

        if 'platform_style_preferences' in insights:
            print(f"\n  Your style preferences:")
            for platform, styles in insights['platform_style_preferences'].items():
                print(f"    {platform}:")
                for style, count in sorted(styles.items(), key=lambda x: x[1], reverse=True):
                    print(f"      - {style}: {count} times")

    save_session(session_data, "complete")

    print("\n✓ Session saved")
    print("\nDone! 🎉")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n⚠️  Interrupted by user")
        sys.exit(0)
