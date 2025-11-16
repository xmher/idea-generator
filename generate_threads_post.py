#!/usr/bin/env python3
# generate_threads_post.py
# Generate Threads posts from article text

import os
import sys
import argparse
from datetime import datetime, timezone

import anthropic

try:
    from dotenv import load_dotenv
    load_dotenv()
except Exception:
    pass

import social_prompts as SP

# --- Setup ---
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")

def generate_threads_post(article_text: str, stream: str = "advertising") -> str:
    """
    Generate a Threads post from article text.

    Args:
        article_text: The full article text to promote
        stream: Either 'advertising' or 'romantasy'

    Returns:
        Generated Threads post text
    """
    if not ANTHROPIC_API_KEY:
        raise ValueError("ANTHROPIC_API_KEY not found in environment")

    # Select appropriate prompt
    if stream == "advertising":
        prompt = SP.THREADS_ADVERTISING_PROMPT.format(article_text=article_text)
    elif stream == "romantasy":
        prompt = SP.THREADS_ROMANTASY_PROMPT.format(article_text=article_text)
    else:
        raise ValueError(f"Unknown stream: {stream}. Use 'advertising' or 'romantasy'")

    # Call Claude
    print(f"🧵 Generating Threads post for {stream} stream...")

    anthropic_client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
    response = anthropic_client.messages.create(
        model="claude-sonnet-4-5",
        max_tokens=2000,
        messages=[{
            "role": "user",
            "content": prompt
        }]
    )

    post_text = response.content[0].text.strip()

    return post_text

def read_article_from_stdin() -> str:
    """Read article text from stdin (for piping)"""
    print("📝 Reading article text from stdin...")
    print("(Paste your article text, then press Ctrl+D on a new line to finish)\n")
    return sys.stdin.read().strip()

def main():
    parser = argparse.ArgumentParser(
        description="Generate Threads posts from article text",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Interactive mode (paste article when prompted):
  python generate_threads_post.py --stream advertising

  # Pipe from file:
  cat article.txt | python generate_threads_post.py --stream romantasy

  # Pass article as argument:
  python generate_threads_post.py --stream advertising --text "Your article text here..."
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
        help="Save to file instead of printing to console"
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
        post_text = generate_threads_post(article_text, args.stream)

        # Display results
        print("\n" + "="*60)
        print(f"🧵 THREADS POST ({args.stream.upper()})")
        print("="*60 + "\n")
        print(post_text)
        print("\n" + "="*60)

        # Save if requested
        if args.output:
            with open(args.output, 'w', encoding='utf-8') as f:
                f.write(post_text)
            print(f"\n✅ Saved to: {args.output}")
        else:
            # Also save with timestamp
            timestamp = datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')
            filename = f"threads_post_{args.stream}_{timestamp}.txt"
            with open(filename, 'w', encoding='utf-8') as f:
                f.write(post_text)
            print(f"\n💾 Auto-saved to: {filename}")

    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
