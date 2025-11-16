#!/usr/bin/env python3
# generate_twitter_post.py
# Generate Twitter posts with Canva template integration

import os
import sys
import json
import argparse
from datetime import datetime, timezone

import anthropic
import requests

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

import social_prompts as SP

# --- Setup ---
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")  # For Gemini image generation

def generate_twitter_post(article_text: str, stream: str = "advertising") -> dict:
    """
    Generate a Twitter post from article text.

    Args:
        article_text: The full article text to promote
        stream: Either 'advertising' or 'romantasy'

    Returns:
        Dict with tweet_text, canva_headline, and canva_stat/canva_subtext
    """
    if not ANTHROPIC_API_KEY:
        raise ValueError("ANTHROPIC_API_KEY not found in environment")

    # Select appropriate prompt
    if stream == "advertising":
        prompt = SP.TWITTER_ADVERTISING_PROMPT.format(article_text=article_text)
    elif stream == "romantasy":
        prompt = SP.TWITTER_ROMANTASY_PROMPT.format(article_text=article_text)
    else:
        raise ValueError(f"Unknown stream: {stream}. Use 'advertising' or 'romantasy'")

    # Call Claude with JSON mode
    print(f"🐦 Generating Twitter post for {stream} stream...")

    anthropic_client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
    response = anthropic_client.messages.create(
        model="claude-sonnet-4-5",
        max_tokens=2000,
        messages=[{
            "role": "user",
            "content": prompt
        }]
    )

    # Parse JSON response
    response_text = response.content[0].text.strip()

    # Extract JSON from markdown code blocks if present
    if "```json" in response_text:
        response_text = response_text.split("```json")[1].split("```")[0].strip()
    elif "```" in response_text:
        response_text = response_text.split("```")[1].split("```")[0].strip()

    post_data = json.loads(response_text)

    return post_data

def generate_social_image(headline: str, stat_or_subtext: str, stream: str = "advertising") -> str:
    """
    Generate a social media image with text using Gemini.

    Args:
        headline: The main headline text
        stat_or_subtext: The stat (advertising) or subtext (romantasy)
        stream: Either 'advertising' or 'romantasy'

    Returns:
        Path to the saved image file
    """
    if not GENAI_AVAILABLE:
        raise RuntimeError("google-genai library not installed. Run: pip install google-genai")

    if not GOOGLE_API_KEY:
        raise ValueError("GOOGLE_API_KEY not found in environment")

    print(f"🎨 Generating social media image for {stream} stream...")

    # Create Gemini client
    client = genai.Client(api_key=GOOGLE_API_KEY)

    # Create design prompt based on stream
    if stream == "advertising":
        # The Viral Edit - Professional, data-driven, bold
        design_prompt = f"""Create a professional, bold Twitter social media graphic for an advertising industry newsletter called "The Viral Edit".

Design requirements:
- Aspect ratio: 16:9 landscape (perfect for Twitter)
- Style: Modern, clean, professional with bold typography
- Color scheme: Dark background (deep navy or charcoal) with bright accent colors (electric blue, neon green, or vibrant orange)
- Layout: Two-thirds rule - text on left 2/3, abstract geometric design on right 1/3

Text to include (must be clearly legible):
1. Main headline (large, bold, sans-serif): "{headline}"
2. Supporting stat (medium size, highlighted): "{stat_or_subtext}"
3. Small "THE VIRAL EDIT" branding in bottom corner

Typography: Use a bold, modern sans-serif font. The headline should be the dominant element.
Visual elements: Abstract geometric shapes, subtle gradients, or data visualization elements (charts, graphs) in the background. Professional but eye-catching.
Overall mood: Authoritative, data-driven, trustworthy but with energy."""

    else:  # romantasy
        # Plot Brew - Warm, magical, community-focused
        design_prompt = f"""Create a warm, magical Twitter social media graphic for a romantasy writing newsletter called "Plot Brew".

Design requirements:
- Aspect ratio: 16:9 landscape (perfect for Twitter)
- Style: Whimsical yet sophisticated, with fantasy elements
- Color scheme: Warm jewel tones (deep burgundy, forest green, gold accents) or soft twilight colors (purple, rose gold, midnight blue)
- Layout: Text centered or slightly left, with magical/fantasy elements framing it

Text to include (must be clearly legible):
1. Main headline (elegant, serif or script font): "{headline}"
2. Supporting text (complementary font): "{stat_or_subtext}"
3. Small "PLOT BREW" branding with a small book or quill icon

Typography: Mix of elegant serif for headlines and clean sans-serif for supporting text. Romantic but readable.
Visual elements: Subtle fantasy elements like starbursts, constellation patterns, book spines, quill pens, or elegant botanical illustrations. Avoid being too busy.
Overall mood: Warm, inviting, creative, slightly magical. Should feel like a cozy book club meets fantasy world."""

    try:
        # Generate image with Gemini
        response = client.models.generate_content(
            model="gemini-2.5-flash-image",
            contents=[design_prompt],
            config=types.GenerateContentConfig(
                response_modalities=['Image'],  # Image only
                image_config=types.ImageConfig(
                    aspect_ratio="16:9",  # Perfect for Twitter
                )
            )
        )

        # Save the generated image
        timestamp = datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')
        image_filename = f"twitter_image_{stream}_{timestamp}.png"

        for part in response.parts:
            if part.inline_data is not None:
                image = part.as_image()
                image.save(image_filename)
                print(f"✅ Image saved: {image_filename}")
                return image_filename

        raise RuntimeError("No image generated in response")

    except Exception as e:
        raise RuntimeError(f"Gemini image generation failed: {e}")

def read_article_from_stdin() -> str:
    """Read article text from stdin (for piping)"""
    print("📝 Reading article text from stdin...")
    print("(Paste your article text, then press Ctrl+D on a new line to finish)\n")
    return sys.stdin.read().strip()

def main():
    parser = argparse.ArgumentParser(
        description="Generate Twitter posts from article text with optional AI-generated images",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Interactive mode (paste article when prompted):
  python generate_twitter_post.py --stream advertising

  # Generate with AI image (requires GOOGLE_API_KEY):
  python generate_twitter_post.py --stream advertising --generate-image

  # Pipe from file with image generation:
  cat article.txt | python generate_twitter_post.py --stream romantasy --generate-image

  # Pass article as argument:
  python generate_twitter_post.py --stream advertising --text "Your article text..."

  # Save to specific file:
  python generate_twitter_post.py --stream advertising --output my_tweet.json

Environment Variables:
  ANTHROPIC_API_KEY - Required for post generation
  GOOGLE_API_KEY - Required for image generation (--generate-image)

Output:
  - Tweet text (ready to post)
  - Template text (headline, stat/subtext)
  - JSON file saved with timestamp
  - PNG image (if --generate-image is used)
        """
    )

    parser.add_argument(
        "--stream",
        choices=["advertising", "romantasy"],
        default="advertising",
        help="Which blog stream (advertising or romantasy)"
    )

    parser.add_argument(
        "--text",
        type=str,
        help="Article text (if not provided, will read from stdin)"
    )

    parser.add_argument(
        "--output",
        type=str,
        help="Save to JSON file instead of just printing"
    )

    parser.add_argument(
        "--generate-image",
        action="store_true",
        help="Generate social media image using Gemini AI (requires GOOGLE_API_KEY)"
    )

    args = parser.parse_args()

    # Get article text
    if args.text:
        article_text = args.text
    else:
        article_text = read_article_from_stdin()

    if not article_text:
        print("ERROR: No article text provided")
        sys.exit(1)

    # Generate post
    try:
        post_data = generate_twitter_post(article_text, args.stream)

        # Display results
        print("\n" + "="*60)
        print(f"🐦 TWITTER POST ({args.stream.upper()})")
        print("="*60 + "\n")

        print("📱 TWEET TEXT:")
        print("-" * 60)
        print(post_data.get("tweet_text", ""))
        print("-" * 60)
        print(f"Character count: {len(post_data.get('tweet_text', ''))}")

        print("\n🎨 DESIGN TEMPLATE TEXT:")
        print("-" * 60)
        print(f"Headline: {post_data.get('canva_headline', '')}")

        if args.stream == "advertising":
            stat = post_data.get('canva_stat')
            if stat:
                print(f"Stat: {stat}")
            else:
                print("Stat: (not applicable)")
        else:  # romantasy
            subtext = post_data.get('canva_subtext', '')
            print(f"Subtext: {subtext}")

        print("-" * 60)

        # Generate image if requested
        image_filename = None
        if args.generate_image:
            try:
                headline = post_data.get('canva_headline', '')
                stat_or_subtext = post_data.get('canva_stat') if args.stream == "advertising" else post_data.get('canva_subtext', '')

                if headline and stat_or_subtext:
                    print("\n🎨 GENERATING AI IMAGE...")
                    print("-" * 60)
                    image_filename = generate_social_image(headline, stat_or_subtext, args.stream)
                    print(f"🖼️  Image ready: {image_filename}")
                    print("-" * 60)
                else:
                    print("\n⚠️  Cannot generate image: missing headline or stat/subtext")
            except Exception as img_error:
                print(f"\n⚠️  Image generation failed: {img_error}")
                print("   Continuing without image...")

        if not args.generate_image:
            print("\n💡 Copy these values into your design tool (Canva, Figma, Bannerbear, etc.)")
            print("   Or use --generate-image to auto-generate with Gemini AI!")

        print("\n" + "="*60)

        # Save JSON
        if args.output:
            output_file = args.output
        else:
            # Auto-save with timestamp
            timestamp = datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')
            output_file = f"twitter_post_{args.stream}_{timestamp}.json"

        # Add image filename to JSON if generated
        if image_filename:
            post_data['generated_image'] = image_filename

        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(post_data, f, indent=2, ensure_ascii=False)

        print(f"💾 Text saved to: {output_file}")
        if image_filename:
            print(f"🖼️  Image saved to: {image_filename}")
            print(f"\n✅ Ready to post! Upload {image_filename} to Twitter with the tweet text above.")

    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    main()
