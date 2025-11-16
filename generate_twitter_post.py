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

import social_prompts as SP
from canva_helper import CanvaHelper

# --- Setup ---
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")
CANVA_API_KEY = os.getenv("CANVA_API_KEY")  # Optional

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

def update_canva_template(design_id: str, updates: dict, stream: str, export: bool = True) -> dict:
    """
    Update a Canva template with new text.

    Args:
        design_id: The Canva design/template ID
        updates: Dict with keys from the AI response (canva_headline, canva_stat, etc.)
        stream: advertising or romantasy (for field mapping)
        export: Whether to export the design as PNG after updating

    Returns:
        Dict with status, URLs, and any error messages
    """
    if not CANVA_API_KEY:
        return {
            "status": "no_api_key",
            "message": "⚠️  Canva API key not configured. Update template manually.",
            "manual_updates": updates
        }

    # Map our fields to Canva template text elements
    # IMPORTANT: These names must match the text placeholders in your Canva template
    # You can customize these based on your actual template structure
    if stream == "advertising":
        element_mapping = {
            "canva_headline": "Headline",  # Change to match your template
            "canva_stat": "Stat"           # Change to match your template
        }
    else:  # romantasy
        element_mapping = {
            "canva_headline": "Headline",  # Change to match your template
            "canva_subtext": "Subtext"     # Change to match your template
        }

    # Build Canva autofill data
    canva_data = {}
    for key, element_name in element_mapping.items():
        if key in updates and updates[key]:
            canva_data[element_name] = updates[key]

    try:
        helper = CanvaHelper()

        # Create a title for the new design
        timestamp = datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M')
        title = f"Twitter Post - {stream.title()} - {timestamp}"

        print(f"📝 Updating Canva template with:")
        for element, text in canva_data.items():
            print(f"   - {element}: {text}")

        # Update and export
        result = helper.update_and_export(
            template_id=design_id,
            updates=canva_data,
            export_format="png" if export else None,
            new_title=title
        )

        return {
            "status": "success",
            "design_id": result["design_id"],
            "edit_url": result.get("edit_url"),
            "export": result.get("export"),
            "message": f"✅ Template updated! Edit at: {result.get('edit_url')}"
        }

    except Exception as e:
        return {
            "status": "error",
            "message": f"❌ Canva API error: {e}",
            "manual_updates": updates
        }

def read_article_from_stdin() -> str:
    """Read article text from stdin (for piping)"""
    print("📝 Reading article text from stdin...")
    print("(Paste your article text, then press Ctrl+D on a new line to finish)\n")
    return sys.stdin.read().strip()

def main():
    parser = argparse.ArgumentParser(
        description="Generate Twitter posts with Canva template integration",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Interactive mode (paste article when prompted):
  python generate_twitter_post.py --stream advertising

  # With Canva template update:
  python generate_twitter_post.py --stream advertising --canva-design ABC123

  # Pipe from file:
  cat article.txt | python generate_twitter_post.py --stream romantasy

  # Pass article as argument:
  python generate_twitter_post.py --stream advertising --text "Your article text..."

Environment Variables:
  ANTHROPIC_API_KEY - Required for post generation
  CANVA_API_KEY - Optional for Canva template updates
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
        "--canva-design",
        type=str,
        help="Canva design/template ID to update"
    )

    parser.add_argument(
        "--output",
        type=str,
        help="Save to JSON file instead of just printing"
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

        print("\n🎨 CANVA TEMPLATE TEXT:")
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

        # Update Canva template if requested
        canva_result = None
        if args.canva_design:
            print("\n🎨 UPDATING CANVA TEMPLATE...")
            canva_result = update_canva_template(args.canva_design, post_data, args.stream)
            print(canva_result.get("message", ""))

            if canva_result.get("status") == "success":
                if canva_result.get("edit_url"):
                    print(f"   Edit URL: {canva_result['edit_url']}")
                if canva_result.get("export"):
                    export_info = canva_result["export"]
                    if isinstance(export_info, dict) and export_info.get("url"):
                        print(f"   Download: {export_info['url']}")
        else:
            print("\n💡 TIP: Use --canva-design DESIGN_ID to auto-update Canva template")

        print("\n" + "="*60)

        # Save if requested
        if args.output:
            output_file = args.output
        else:
            # Auto-save with timestamp
            timestamp = datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')
            output_file = f"twitter_post_{args.stream}_{timestamp}.json"

        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(post_data, f, indent=2, ensure_ascii=False)

        print(f"💾 Saved to: {output_file}")

    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    main()
