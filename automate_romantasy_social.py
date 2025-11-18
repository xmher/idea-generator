#!/usr/bin/env python3
# automate_romantasy_social.py
# Automated social media posting for romantasy writing advice

import os
import sys
import json
import argparse
import smtplib
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.image import MIMEImage
from pathlib import Path

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

# --- Configuration ---
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
APILAYER_API_KEY = os.getenv("APILAYER_API_KEY")

# Email configuration for Instagram delivery
EMAIL_FROM = os.getenv("EMAIL_FROM", "")
EMAIL_TO = os.getenv("EMAIL_TO", "")
SMTP_HOST = os.getenv("SMTP_HOST", "smtp.gmail.com")
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
SMTP_USER = os.getenv("SMTP_USER", "")
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD", "")

if not ANTHROPIC_API_KEY:
    print("ERROR: ANTHROPIC_API_KEY not configured")
    sys.exit(1)

if not GOOGLE_API_KEY:
    print("WARNING: GOOGLE_API_KEY not configured. Image generation will be disabled.")

anthropic_client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)

# Platform character limits
PLATFORM_LIMITS = {
    "twitter": 280,
    "threads": 500,
    "pinterest": 500,  # Pin description
    "instagram": 2200
}

def generate_writing_advice_topic() -> str:
    """
    Generate a writing advice topic for romantasy writers using Claude
    """
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

    try:
        response = anthropic_client.messages.create(
            model="claude-sonnet-4-5",
            max_tokens=200,
            messages=[{"role": "user", "content": prompt}]
        )
        topic = response.content[0].text.strip()
        # Remove quotes if present
        topic = topic.strip('"').strip("'")
        return topic
    except Exception as e:
        print(f"ERROR generating topic: {e}")
        return "How to Write Compelling Romantic Tension in Fantasy Settings"

def generate_social_posts(topic: str) -> Dict[str, str]:
    """
    Generate platform-specific posts for Twitter, Threads, Pinterest, and Instagram
    """
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

1. **TWITTER (280 chars max)**
   - Hook with vulnerability or craft insight
   - 2-3 short lines
   - Question or CTA at end
   - 1-2 emojis (✨💫📚🗡️❤️)

2. **THREADS (500 chars max)**
   - Longer, conversational format
   - Personal story or struggle
   - 3-4 craft insights
   - Community question at end
   - More casual tone

3. **PINTEREST (500 chars)**
   - Educational and keyword-rich
   - List format or "How to" structure
   - Include specific romantasy examples
   - Optimize for search (use keywords)
   - Professional but approachable

4. **INSTAGRAM (2200 chars max)**
   - Longest, most personal
   - Story-driven opening
   - 5-7 actionable tips/insights
   - Examples from popular romantasy books
   - Strong community call-to-action
   - Use line breaks for readability
   - 3-5 relevant hashtags at end

---

Return ONLY this JSON format:

{{
  "twitter": "Your Twitter post here (max 280 chars)",
  "threads": "Your Threads post here (max 500 chars)",
  "pinterest": "Your Pinterest description here (max 500 chars)",
  "instagram": "Your Instagram caption here (max 2200 chars)"
}}
"""

    try:
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

        # Find JSON in response
        start = result_text.find("{")
        end = result_text.rfind("}") + 1
        if start != -1 and end > start:
            result_text = result_text[start:end]

        posts = json.loads(result_text)
        return posts

    except Exception as e:
        print(f"ERROR generating social posts: {e}")
        return {
            "twitter": f"✨ {topic} #WritingTips #Romantasy",
            "threads": f"Let's talk about {topic.lower()}...",
            "pinterest": f"Writing Advice: {topic}",
            "instagram": f"Today's writing tip: {topic}\n\n#WritingCommunity #Romantasy"
        }

def generate_image_prompt(topic: str, platform: str) -> str:
    """
    Generate an image prompt for Gemini based on the topic and platform
    """
    prompt = f"""Create a detailed image generation prompt for a social media graphic about romantasy writing advice.

**TOPIC:** {topic}

**PLATFORM:** {platform}

**BRAND: "Plot Brew"**
- Visual Style: Warm, magical, whimsical yet sophisticated
- Color Palette: Warm jewel tones (burgundy, forest green, gold) OR twilight colors (purple, rose gold, midnight blue)
- Typography: Mix of elegant serif for headlines and clean sans-serif for body text
- Visual Elements: Subtle fantasy elements (starbursts, constellations, book spines, quill pens, botanical illustrations)
- Mood: Warm, inviting, creative, slightly magical
- Branding: Include "PLOT BREW" text in elegant font

**PLATFORM SPECS:**
- Twitter/Threads: 16:9 landscape
- Pinterest: 2:3 vertical (Pinterest optimized)
- Instagram: 1:1 square

**TEXT TO INCLUDE:**
- Main headline: "{topic}"
- Small "Plot Brew" branding

**YOUR TASK:**
Create a Gemini AI image prompt that produces a beautiful, on-brand graphic.

Be specific about:
- Visual metaphors related to the writing topic
- Color scheme and mood
- Text placement and typography
- Fantasy/romantic elements

Return ONLY the image generation prompt (start with "Create a...").
"""

    try:
        response = anthropic_client.messages.create(
            model="claude-sonnet-4-5",
            max_tokens=800,
            messages=[{"role": "user", "content": prompt}]
        )

        image_prompt = response.content[0].text.strip()
        return image_prompt

    except Exception as e:
        print(f"ERROR generating image prompt: {e}")
        return f"Create a warm, magical social media graphic for romantasy writers about {topic}. Use purple and gold colors with subtle fantasy elements."

def generate_image(image_prompt: str, platform: str) -> Optional[str]:
    """
    Generate an image using Gemini
    """
    if not GENAI_AVAILABLE or not GOOGLE_API_KEY:
        print("⚠️  Image generation not available (missing google-genai or GOOGLE_API_KEY)")
        return None

    print(f"🎨 Generating {platform} image with Gemini...")

    # Set aspect ratio based on platform
    aspect_ratios = {
        "twitter": "16:9",
        "threads": "16:9",
        "pinterest": "2:3",
        "instagram": "1:1"
    }

    aspect_ratio = aspect_ratios.get(platform, "1:1")

    try:
        client = genai.Client(api_key=GOOGLE_API_KEY)

        response = client.models.generate_content(
            model="gemini-2.5-flash-image",
            contents=[image_prompt],
            config=types.GenerateContentConfig(
                response_modalities=['Image'],
                image_config=types.ImageConfig(
                    aspect_ratio=aspect_ratio
                )
            )
        )

        # Save image
        timestamp = datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')
        image_filename = f"romantasy_{platform}_{timestamp}.png"

        for part in response.parts:
            if part.inline_data is not None:
                image = part.as_image()
                image.save(image_filename)
                print(f"  ✓ Image saved: {image_filename}")
                return image_filename

        print("  ✗ No image generated")
        return None

    except Exception as e:
        print(f"  ✗ Image generation failed: {e}")
        return None

def post_to_social_media(platform: str, text: str, image_path: Optional[str] = None) -> bool:
    """
    Post to social media using apilayer Social Media Assets Generator API

    Note: This is a placeholder implementation. You'll need to:
    1. Check apilayer's actual API documentation
    2. May need different APIs for different platforms
    3. Configure authentication for each platform
    """
    if not APILAYER_API_KEY:
        print(f"  ⚠️  APILAYER_API_KEY not configured. Skipping {platform} post.")
        return False

    print(f"📤 Posting to {platform}...")

    # This is a placeholder - actual implementation depends on apilayer API structure
    # You may need to use platform-specific APIs or OAuth tokens

    """
    Example structure (adjust based on actual API):

    headers = {
        "apikey": APILAYER_API_KEY
    }

    data = {
        "platform": platform,
        "text": text,
        "image": image_path
    }

    response = requests.post(
        "https://api.apilayer.com/social_media_assets_generator/post",
        headers=headers,
        json=data
    )

    if response.status_code == 200:
        print(f"  ✓ Posted to {platform}")
        return True
    else:
        print(f"  ✗ Failed to post to {platform}: {response.text}")
        return False
    """

    # For now, just save to file for manual posting
    print(f"  💾 [DRY RUN] Would post to {platform}:")
    print(f"     Text: {text[:100]}...")
    if image_path:
        print(f"     Image: {image_path}")

    return True

def email_instagram_post(text: str, image_path: Optional[str] = None) -> bool:
    """
    Email the Instagram post content instead of auto-posting
    """
    if not all([EMAIL_FROM, EMAIL_TO, SMTP_USER, SMTP_PASSWORD]):
        print("  ⚠️  Email not configured. Skipping Instagram email.")
        print(f"     Text: {text[:100]}...")
        if image_path:
            print(f"     Image: {image_path}")
        return False

    print(f"📧 Emailing Instagram post to {EMAIL_TO}...")

    try:
        # Create message
        msg = MIMEMultipart()
        msg['From'] = EMAIL_FROM
        msg['To'] = EMAIL_TO
        msg['Subject'] = f"Plot Brew Instagram Post - {datetime.now().strftime('%Y-%m-%d')}"

        # Email body
        body = f"""Plot Brew Instagram Post Ready to Publish

CAPTION:
{text}

---

Attached: Instagram image (if generated)

To post:
1. Save the attached image
2. Open Instagram app
3. Create new post
4. Upload image
5. Copy/paste caption above
6. Post!
"""

        msg.attach(MIMEText(body, 'plain'))

        # Attach image if available
        if image_path and os.path.exists(image_path):
            with open(image_path, 'rb') as f:
                img_data = f.read()
                image = MIMEImage(img_data, name=os.path.basename(image_path))
                msg.attach(image)

        # Send email
        with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as server:
            server.starttls()
            server.login(SMTP_USER, SMTP_PASSWORD)
            server.send_message(msg)

        print(f"  ✓ Email sent successfully")
        return True

    except Exception as e:
        print(f"  ✗ Email failed: {e}")
        return False

def main():
    parser = argparse.ArgumentParser(
        description="Automate social media posting for romantasy writing advice",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
This script will:
1. Generate a writing advice topic (or use provided topic)
2. Create platform-specific posts for Twitter, Threads, Pinterest, Instagram
3. Generate custom images for each platform using Gemini
4. Auto-post to Twitter, Threads, Pinterest (via apilayer API)
5. Email Instagram post for manual posting

Environment Variables Required:
  ANTHROPIC_API_KEY - For content generation
  GOOGLE_API_KEY - For image generation (Gemini)
  APILAYER_API_KEY - For social media posting (optional)
  EMAIL_FROM, EMAIL_TO - For Instagram email delivery
  SMTP_USER, SMTP_PASSWORD - Email credentials

Examples:
  # Auto-generate topic and post to all platforms:
  python automate_romantasy_social.py

  # Use specific topic:
  python automate_romantasy_social.py --topic "How to Write Enemies-to-Lovers Banter"

  # Generate content only, don't post:
  python automate_romantasy_social.py --dry-run

  # Skip image generation:
  python automate_romantasy_social.py --no-images
        """
    )

    parser.add_argument(
        "--topic",
        type=str,
        help="Specific writing advice topic (auto-generated if not provided)"
    )

    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Generate content but don't post to social media"
    )

    parser.add_argument(
        "--no-images",
        action="store_true",
        help="Skip image generation"
    )

    parser.add_argument(
        "--platforms",
        nargs='+',
        choices=['twitter', 'threads', 'pinterest', 'instagram'],
        default=['twitter', 'threads', 'pinterest', 'instagram'],
        help="Which platforms to post to (default: all)"
    )

    args = parser.parse_args()

    print("="*80)
    print("ROMANTASY SOCIAL MEDIA AUTOMATION")
    print("Plot Brew - Writing Advice for Romantasy Authors")
    if args.dry_run:
        print("[DRY RUN MODE]")
    print("="*80 + "\n")

    # Step 1: Get topic
    if args.topic:
        topic = args.topic
        print(f"📝 Using provided topic: {topic}\n")
    else:
        print("🎲 Generating writing advice topic...")
        topic = generate_writing_advice_topic()
        print(f"✓ Topic: {topic}\n")

    # Step 2: Generate social posts
    print("✍️  Generating platform-specific posts...")
    posts = generate_social_posts(topic)

    print("\n" + "="*80)
    print("GENERATED CONTENT")
    print("="*80 + "\n")

    for platform in args.platforms:
        print(f"📱 {platform.upper()}")
        print("-"*80)
        print(posts.get(platform, "N/A"))
        print(f"Characters: {len(posts.get(platform, ''))}/{PLATFORM_LIMITS[platform]}")
        print()

    # Step 3: Generate images
    images = {}
    if not args.no_images:
        print("="*80)
        print("GENERATING IMAGES")
        print("="*80 + "\n")

        for platform in args.platforms:
            print(f"Generating {platform} image...")
            image_prompt = generate_image_prompt(topic, platform)
            image_path = generate_image(image_prompt, platform)

            if image_path:
                images[platform] = image_path
            print()

    # Step 4: Post to platforms
    if not args.dry_run:
        print("="*80)
        print("POSTING TO SOCIAL MEDIA")
        print("="*80 + "\n")

        for platform in args.platforms:
            post_text = posts.get(platform, "")
            image_path = images.get(platform)

            if platform == "instagram":
                # Email Instagram instead of posting
                email_instagram_post(post_text, image_path)
            else:
                # Post to other platforms
                post_to_social_media(platform, post_text, image_path)

            print()

    # Step 5: Save report
    timestamp = datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')
    report_file = f"social_media_report_{timestamp}.json"

    report = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "topic": topic,
        "platforms": args.platforms,
        "posts": posts,
        "images": images,
        "dry_run": args.dry_run
    }

    with open(report_file, 'w', encoding='utf-8') as f:
        json.dump(report, f, indent=2, ensure_ascii=False)

    print("="*80)
    print(f"💾 Report saved: {report_file}")
    print("="*80)

    if args.dry_run:
        print("\n💡 Run without --dry-run to actually post to social media")

    print("\n✅ Social media automation complete!\n")

if __name__ == "__main__":
    main()
