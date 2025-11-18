#!/usr/bin/env python3
# automate_romantasy_social_interactive.py
# Interactive social media automation with human-in-the-loop review

import os
import sys
import json
import smtplib
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional
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
    from google import genai
    from google.genai import types
    GENAI_AVAILABLE = True
except ImportError:
    GENAI_AVAILABLE = False
    print("WARNING: google-genai not installed. Image generation unavailable.")
    print("Install with: pip install google-genai")

# Optional: Twitter API (tweepy)
try:
    import tweepy
    TWEEPY_AVAILABLE = True
except ImportError:
    TWEEPY_AVAILABLE = False
    print("INFO: tweepy not installed. Twitter auto-posting unavailable.")
    print("Install with: pip install tweepy")

# --- Configuration ---
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
APILAYER_API_KEY = os.getenv("APILAYER_API_KEY")

# Twitter API v2 OAuth 2.0
TWITTER_API_KEY = os.getenv("TWITTER_API_KEY")
TWITTER_API_SECRET = os.getenv("TWITTER_API_SECRET")
TWITTER_ACCESS_TOKEN = os.getenv("TWITTER_ACCESS_TOKEN")
TWITTER_ACCESS_SECRET = os.getenv("TWITTER_ACCESS_SECRET")
TWITTER_BEARER_TOKEN = os.getenv("TWITTER_BEARER_TOKEN")

# Meta Graph API (for Threads)
META_ACCESS_TOKEN = os.getenv("META_ACCESS_TOKEN")
META_USER_ID = os.getenv("META_USER_ID")

# Pinterest API v5
PINTEREST_ACCESS_TOKEN = os.getenv("PINTEREST_ACCESS_TOKEN")
PINTEREST_BOARD_ID = os.getenv("PINTEREST_BOARD_ID")

# Email for Instagram
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

# Platform character limits
PLATFORM_LIMITS = {
    "twitter": 280,
    "threads": 500,
    "pinterest": 500,
    "instagram": 2200
}

# ==================== INTERACTIVE HELPERS ====================

def prompt_user(message: str, options: List[str]) -> str:
    """Interactive prompt with options"""
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

def confirm_action(message: str) -> bool:
    """Ask user to confirm an action"""
    response = input(f"\n{message} (y/n): ").strip().lower()
    return response in ['y', 'yes']

def get_user_input(prompt_text: str, default: str = "") -> str:
    """Get text input from user"""
    if default:
        user_input = input(f"\n{prompt_text} (press Enter for: {default[:50]}...): ").strip()
        return user_input if user_input else default
    else:
        return input(f"\n{prompt_text}: ").strip()

# ==================== CONTENT GENERATION ====================

def generate_writing_advice_topic() -> str:
    """Generate a writing advice topic for romantasy writers"""
    prompt = """You are a content strategist for "Plot Brew," a writing advice platform for romantasy authors.

Generate ONE specific, actionable writing advice topic that would be valuable for romantasy writers.

**Topic Guidelines:**
- Specific to romantasy genre (not generic writing advice)
- Actionable and practical
- Addresses craft, structure, or reader expectations
- Can be explained in a social media post

**Good Topics:**
- "How to Write Sexual Tension Without Explicit Scenes"
- "The 3-Act Structure for Dual-Plot Romantasy"
- "Why Your Magic System Needs Relationship Stakes"
- "Writing Morally Grey Love Interests Readers Will Root For"
- "How to Balance World-Building Without Info-Dumping"

Return ONLY the topic as a single sentence (no quotation marks, no preamble).
"""

    response = anthropic_client.messages.create(
        model="claude-sonnet-4-5",
        max_tokens=200,
        messages=[{"role": "user", "content": prompt}]
    )
    topic = response.content[0].text.strip().strip('"').strip("'")
    return topic

def generate_social_posts(topic: str) -> Dict[str, str]:
    """Generate platform-specific posts"""
    prompt = f"""You are creating social media posts for "Plot Brew," a romantasy writing advice platform.

**TOPIC:** {topic}

**YOUR VOICE:**
- Personal and vulnerable (share writing journey)
- Celebratory of romantasy (treat it with intellectual respect)
- Community-focused ("we" language, not "you")
- Geeky enthusiasm about tropes and craft
- Relatable struggles of writing life

---

**GENERATE POSTS FOR 4 PLATFORMS:**

1. **TWITTER (280 chars max)** - Hook + craft insight + question
2. **THREADS (500 chars max)** - Personal story + insights + community question
3. **PINTEREST (500 chars)** - Educational, keyword-rich, list format
4. **INSTAGRAM (2200 chars max)** - Story-driven + 5-7 tips + hashtags

Return ONLY this JSON format:

{{
  "twitter": "Your Twitter post here",
  "threads": "Your Threads post here",
  "pinterest": "Your Pinterest description here",
  "instagram": "Your Instagram caption here"
}}
"""

    response = anthropic_client.messages.create(
        model="claude-sonnet-4-5",
        max_tokens=2500,
        messages=[{"role": "user", "content": prompt}]
    )

    result_text = response.content[0].text.strip()

    # Extract JSON
    if "```json" in result_text:
        result_text = result_text.split("```json")[1].split("```")[0].strip()
    elif "```" in result_text:
        result_text = result_text.split("```")[1].split("```")[0].strip()

    start = result_text.find("{")
    end = result_text.rfind("}") + 1
    if start != -1 and end > start:
        result_text = result_text[start:end]

    return json.loads(result_text)

def generate_image_prompt(topic: str, platform: str) -> str:
    """Generate image prompt for Gemini"""
    aspect_ratios = {"twitter": "16:9", "threads": "16:9", "pinterest": "2:3", "instagram": "1:1"}
    aspect_ratio = aspect_ratios.get(platform, "1:1")

    prompt = f"""Create a detailed image generation prompt for a social media graphic about romantasy writing advice.

**TOPIC:** {topic}
**PLATFORM:** {platform} (aspect ratio: {aspect_ratio})

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

def generate_image(image_prompt: str, platform: str) -> Optional[str]:
    """Generate image using Gemini"""
    if not GENAI_AVAILABLE or not GOOGLE_API_KEY:
        print("⚠️  Image generation not available")
        return None

    aspect_ratios = {"twitter": "16:9", "threads": "16:9", "pinterest": "2:3", "instagram": "1:1"}
    aspect_ratio = aspect_ratios.get(platform, "1:1")

    try:
        client = genai.Client(api_key=GOOGLE_API_KEY)
        response = client.models.generate_content(
            model="gemini-2.5-flash-image",
            contents=[image_prompt],
            config=types.GenerateContentConfig(
                response_modalities=['Image'],
                image_config=types.ImageConfig(aspect_ratio=aspect_ratio)
            )
        )

        timestamp = datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')
        image_filename = f"romantasy_{platform}_{timestamp}.png"

        for part in response.parts:
            if part.inline_data is not None:
                image = part.as_image()
                image.save(image_filename)
                return image_filename

        return None
    except Exception as e:
        print(f"✗ Image generation failed: {e}")
        return None

def format_image_for_platform(image_path: str, platform: str) -> Optional[str]:
    """Format image using apilayer"""
    if not APILAYER_API_KEY or not image_path or not os.path.exists(image_path):
        return image_path

    platform_endpoints = {"twitter": "twitter", "pinterest": "pinterest",
                         "instagram": "instagram", "threads": "twitter"}

    endpoint = platform_endpoints.get(platform)
    if not endpoint:
        return image_path

    try:
        with open(image_path, 'rb') as f:
            files = {'body': f}
            headers = {'apikey': APILAYER_API_KEY}

            response = requests.post(
                f"https://api.apilayer.com/social_media_assets_generator/upload/{endpoint}",
                headers=headers,
                files=files,
                timeout=30
            )

            if response.status_code == 200:
                formatted_filename = image_path.replace('.png', f'_formatted_{platform}.png')
                with open(formatted_filename, 'wb') as out:
                    out.write(response.content)
                return formatted_filename
    except Exception as e:
        print(f"✗ Formatting error: {e}")

    return image_path

# ==================== POSTING FUNCTIONS ====================

def post_to_twitter(text: str, image_path: Optional[str] = None) -> bool:
    """Post to Twitter using API v2"""
    if not all([TWITTER_API_KEY, TWITTER_API_SECRET, TWITTER_ACCESS_TOKEN, TWITTER_ACCESS_SECRET]):
        print("  ⚠️  Twitter API credentials not configured")
        return False

    if not TWEEPY_AVAILABLE:
        print("  ⚠️  tweepy library not installed")
        return False

    try:
        # Twitter API v2 client
        client = tweepy.Client(
            consumer_key=TWITTER_API_KEY,
            consumer_secret=TWITTER_API_SECRET,
            access_token=TWITTER_ACCESS_TOKEN,
            access_token_secret=TWITTER_ACCESS_SECRET
        )

        # Upload media if provided (requires API v1.1)
        media_id = None
        if image_path and os.path.exists(image_path):
            auth = tweepy.OAuth1UserHandler(
                TWITTER_API_KEY, TWITTER_API_SECRET,
                TWITTER_ACCESS_TOKEN, TWITTER_ACCESS_SECRET
            )
            api_v1 = tweepy.API(auth)
            media = api_v1.media_upload(filename=image_path)
            media_id = media.media_id

        # Post tweet
        if media_id:
            response = client.create_tweet(text=text, media_ids=[media_id])
        else:
            response = client.create_tweet(text=text)

        print(f"  ✓ Posted to Twitter: https://twitter.com/i/web/status/{response.data['id']}")
        return True

    except Exception as e:
        print(f"  ✗ Twitter post failed: {e}")
        return False

def post_to_threads(text: str, image_path: Optional[str] = None) -> bool:
    """Post to Threads using Meta Graph API"""
    if not all([META_ACCESS_TOKEN, META_USER_ID]):
        print("  ⚠️  Meta API credentials not configured")
        return False

    try:
        # Threads requires container creation then publishing
        # Step 1: Create media container
        url = f"https://graph.threads.net/v1.0/{META_USER_ID}/threads"

        data = {
            "media_type": "TEXT",
            "text": text,
            "access_token": META_ACCESS_TOKEN
        }

        if image_path and os.path.exists(image_path):
            # For image posts, need to upload image first and get URL
            # This is simplified - you may need to host images somewhere
            data["media_type"] = "IMAGE"
            data["image_url"] = image_path  # Should be publicly accessible URL

        response = requests.post(url, json=data, timeout=30)
        response.raise_for_status()

        container_id = response.json()["id"]

        # Step 2: Publish container
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
        print(f"  ✗ Threads post failed: {e}")
        return False

def post_to_pinterest(text: str, image_path: Optional[str] = None) -> bool:
    """Post to Pinterest using API v5"""
    if not all([PINTEREST_ACCESS_TOKEN, PINTEREST_BOARD_ID]):
        print("  ⚠️  Pinterest API credentials not configured")
        return False

    if not image_path or not os.path.exists(image_path):
        print("  ⚠️  Pinterest requires an image")
        return False

    try:
        url = "https://api.pinterest.com/v5/pins"

        headers = {
            "Authorization": f"Bearer {PINTEREST_ACCESS_TOKEN}",
            "Content-Type": "application/json"
        }

        # Upload image and create pin
        # Note: Simplified - may need to upload image separately
        data = {
            "board_id": PINTEREST_BOARD_ID,
            "description": text,
            "media_source": {
                "source_type": "image_url",
                "url": image_path  # Should be publicly accessible URL
            }
        }

        response = requests.post(url, headers=headers, json=data, timeout=30)
        response.raise_for_status()

        pin_id = response.json()["id"]
        print(f"  ✓ Posted to Pinterest (Pin ID: {pin_id})")
        return True

    except Exception as e:
        print(f"  ✗ Pinterest post failed: {e}")
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

# ==================== MAIN INTERACTIVE FLOW ====================

def main():
    print("="*80)
    print("ROMANTASY SOCIAL MEDIA AUTOMATION (INTERACTIVE)")
    print("Plot Brew - Human-in-the-Loop Content Generation")
    print("="*80)

    # STEP 1: Topic Generation
    print("\n" + "="*80)
    print("STEP 1: TOPIC GENERATION")
    print("="*80)

    topic = None
    while not topic:
        action = prompt_user(
            "What would you like to do?",
            ["Generate a topic automatically", "Provide my own topic"]
        )

        if "Generate" in action:
            print("\n🎲 Generating writing advice topic...")
            topic = generate_writing_advice_topic()
            print(f"\n✨ Generated Topic:\n   {topic}")

            if not confirm_action("Use this topic?"):
                topic = None
                continue
        else:
            topic = get_user_input("Enter your topic")

    print(f"\n✅ Final Topic: {topic}")

    # STEP 2: Generate Posts
    print("\n" + "="*80)
    print("STEP 2: SOCIAL MEDIA POSTS")
    print("="*80)

    posts = {}
    platforms = ["twitter", "threads", "pinterest", "instagram"]

    generate_all = confirm_action("Generate posts for all platforms at once?")

    if generate_all:
        print("\n✍️  Generating posts for all platforms...")
        posts = generate_social_posts(topic)

        print("\n📱 GENERATED POSTS:\n")
        for platform in platforms:
            print(f"{platform.upper()}:")
            print(f"{posts.get(platform, 'N/A')}")
            print(f"Characters: {len(posts.get(platform, ''))}/{PLATFORM_LIMITS[platform]}\n")

        if not confirm_action("Accept all posts?"):
            print("\nLet's regenerate individual platforms...")
            generate_all = False

    if not generate_all:
        for platform in platforms:
            if platform not in posts:
                print(f"\n--- {platform.upper()} ---")
                posts[platform] = generate_social_posts(topic)[platform]

            satisfied = False
            while not satisfied:
                print(f"\n{posts[platform]}")
                print(f"Characters: {len(posts[platform])}/{PLATFORM_LIMITS[platform]}")

                action = prompt_user(
                    f"What would you like to do with this {platform} post?",
                    ["Accept it", "Regenerate", "Edit manually", "Skip this platform"]
                )

                if "Accept" in action:
                    satisfied = True
                elif "Regenerate" in action:
                    print(f"Regenerating {platform} post...")
                    posts[platform] = generate_social_posts(topic)[platform]
                elif "Edit" in action:
                    posts[platform] = get_user_input(f"Enter your {platform} post", posts[platform])
                    satisfied = True
                else:  # Skip
                    del posts[platform]
                    satisfied = True

    print("\n✅ Posts finalized")

    # STEP 3: Generate Images
    print("\n" + "="*80)
    print("STEP 3: IMAGE GENERATION")
    print("="*80)

    generate_images = confirm_action("Generate images?")

    images = {}
    if generate_images:
        for platform in list(posts.keys()):
            print(f"\n--- {platform.upper()} IMAGE ---")

            satisfied = False
            while not satisfied:
                print(f"\n🎨 Generating image prompt for {platform}...")
                image_prompt = generate_image_prompt(topic, platform)

                print(f"\nImage Prompt:\n{image_prompt}")

                action = prompt_user(
                    "What would you like to do?",
                    ["Generate image with this prompt", "Regenerate prompt", "Edit prompt", "Skip image"]
                )

                if "Skip" in action:
                    break
                elif "Regenerate" in action:
                    continue
                elif "Edit" in action:
                    image_prompt = get_user_input("Enter your image prompt", image_prompt)

                # Generate image
                print(f"\n🖼️  Generating {platform} image...")
                image_path = generate_image(image_prompt, platform)

                if image_path:
                    print(f"✓ Image saved: {image_path}")

                    # Format with apilayer
                    if APILAYER_API_KEY:
                        print(f"📐 Formatting for {platform}...")
                        formatted_path = format_image_for_platform(image_path, platform)
                        if formatted_path != image_path:
                            print(f"✓ Formatted: {formatted_path}")
                            image_path = formatted_path

                    images[platform] = image_path

                    if confirm_action("Accept this image?"):
                        satisfied = True
                else:
                    print("✗ Image generation failed")
                    if not confirm_action("Try again?"):
                        break

    # STEP 4: Post to Platforms
    print("\n" + "="*80)
    print("STEP 4: POSTING TO PLATFORMS")
    print("="*80)

    if not confirm_action("Ready to post to social media?"):
        print("\n💾 Content saved. You can post manually later.")
        # Save to files...
        return

    for platform in list(posts.keys()):
        print(f"\n--- {platform.upper()} ---")
        print(f"Post: {posts[platform][:100]}...")
        if platform in images:
            print(f"Image: {images[platform]}")

        if not confirm_action(f"Post to {platform}?"):
            print(f"  ⏭️  Skipped {platform}")
            continue

        # Post to platform
        success = False
        if platform == "twitter":
            success = post_to_twitter(posts[platform], images.get(platform))
        elif platform == "threads":
            success = post_to_threads(posts[platform], images.get(platform))
        elif platform == "pinterest":
            success = post_to_pinterest(posts[platform], images.get(platform))
        elif platform == "instagram":
            success = email_instagram_post(posts[platform], images.get(platform))

    # Save report
    timestamp = datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')
    report_file = f"social_media_report_{timestamp}.json"

    report = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "topic": topic,
        "posts": posts,
        "images": images
    }

    with open(report_file, 'w', encoding='utf-8') as f:
        json.dump(report, f, indent=2, ensure_ascii=False)

    print("\n" + "="*80)
    print(f"✅ Session complete! Report saved: {report_file}")
    print("="*80)

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n⚠️  Session interrupted by user")
        sys.exit(0)
