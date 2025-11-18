#!/usr/bin/env python3
# optimize_article_tags.py
# Delete existing tags and intelligently re-tag articles based on content analysis

import os
import sys
import json
import argparse
from datetime import datetime, timezone
from typing import List, Dict, Any, Set
from collections import defaultdict

import requests
from requests.auth import HTTPBasicAuth
import anthropic
from bs4 import BeautifulSoup

try:
    from dotenv import load_dotenv
    load_dotenv()
except Exception:
    pass

# --- Configuration ---
WP_URL = os.getenv("WP_URL", "").rstrip("/")
WP_USERNAME = os.getenv("WP_USERNAME", "")
WP_APP_PASSWORD = os.getenv("WP_APP_PASSWORD", "")
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")

MIN_ARTICLES_PER_TAG = 10  # Only create tags that have at least 10 articles

if not all([WP_URL, WP_USERNAME, WP_APP_PASSWORD]):
    print("ERROR: WordPress credentials not configured")
    print("Set WP_URL, WP_USERNAME, and WP_APP_PASSWORD environment variables")
    sys.exit(1)

if not ANTHROPIC_API_KEY:
    print("ERROR: ANTHROPIC_API_KEY not configured")
    sys.exit(1)

anthropic_client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)

def wp_auth() -> HTTPBasicAuth:
    return HTTPBasicAuth(WP_USERNAME, WP_APP_PASSWORD)

def strip_html(html_content: str) -> str:
    """Convert HTML to plain text"""
    soup = BeautifulSoup(html_content, 'html.parser')
    return soup.get_text(separator=' ', strip=True)

def get_first_paragraph(content_html: str) -> str:
    """Extract the first paragraph from HTML content"""
    soup = BeautifulSoup(content_html, 'html.parser')

    # Try to find first <p> tag
    first_p = soup.find('p')
    if first_p:
        text = first_p.get_text(strip=True)
        # Limit to ~300 chars for efficiency
        return text[:300]

    # Fallback: get first 300 chars of text
    text = soup.get_text(separator=' ', strip=True)
    return text[:300]

def fetch_all_posts() -> List[Dict[str, Any]]:
    """Fetch all published posts from WordPress"""
    print(f"📥 Fetching posts from {WP_URL}...")

    all_posts = []
    page = 1
    per_page = 100

    while True:
        try:
            response = requests.get(
                f"{WP_URL}/wp-json/wp/v2/posts",
                params={
                    "per_page": per_page,
                    "page": page,
                    "status": "publish",
                    "_fields": "id,title,content,tags"
                },
                auth=wp_auth(),
                timeout=30
            )
            response.raise_for_status()

            posts = response.json()
            if not posts:
                break

            all_posts.extend(posts)
            print(f"  Fetched page {page}: {len(posts)} posts")

            # Check if there are more pages
            total_pages = int(response.headers.get('X-WP-TotalPages', 1))
            if page >= total_pages:
                break

            page += 1

        except requests.RequestException as e:
            print(f"ERROR fetching posts (page {page}): {e}")
            break

    print(f"✅ Total posts fetched: {len(all_posts)}\n")
    return all_posts

def suggest_tags_for_article(title: str, first_paragraph: str) -> List[str]:
    """
    Use Claude to suggest relevant tags for an article based on advertising pillars and formats
    """
    prompt = f"""You are a content strategist for an advertising industry blog focused on:

**PILLARS:**
1. Media Accountability & Performance (ad fraud, measurement, verification, platform accountability)
2. Advertising Strategy & Investment (media buying, cost analysis, risk management, pitch strategies)
3. Advertising Analytics & Automation (Python/SQL automation, dashboards, reporting tools, data pipelines)

**FORMATS:**
1. Investigative/Research Pieces
2. Opinion/Thought Pieces
3. Expert How-To/Guides

**ARTICLE TO TAG:**
Title: {title}

First Paragraph:
{first_paragraph}

---

**YOUR TASK:**
Suggest 3-5 relevant tags for this article. Tags should be:
- Specific and descriptive (not too broad)
- Related to advertising/marketing industry topics
- Useful for grouping similar content
- Lowercase, hyphenated format (e.g., "ad-fraud", "programmatic-advertising")

**Tag Categories to Consider:**
- **Channels:** programmatic-advertising, social-media-ads, tv-advertising, radio-advertising, ooh-advertising, search-ads, display-ads
- **Topics:** ad-fraud, ad-verification, measurement, attribution, media-buying, agency-strategy, campaign-planning
- **Technical:** python-automation, data-analytics, reporting-dashboards, api-integration, excel-automation
- **Platforms:** google-ads, meta-ads, tiktok-ads, amazon-ads, linkedin-ads
- **Concepts:** e-e-a-t, auditing, investment-management, cost-analysis, roi-optimization

Return ONLY a JSON array of tag strings:

["tag-1", "tag-2", "tag-3"]

Keep it to 3-5 most relevant tags.
"""

    try:
        response = anthropic_client.messages.create(
            model="claude-sonnet-4-5",
            max_tokens=500,
            messages=[{
                "role": "user",
                "content": prompt
            }]
        )

        result_text = response.content[0].text.strip()

        # Extract JSON from response
        if "```json" in result_text:
            result_text = result_text.split("```json")[1].split("```")[0].strip()
        elif "```" in result_text:
            result_text = result_text.split("```")[1].split("```")[0].strip()

        # Find JSON array
        start = result_text.find("[")
        end = result_text.rfind("]") + 1
        if start != -1 and end > start:
            result_text = result_text[start:end]

        tags = json.loads(result_text)

        # Normalize tags (lowercase, strip whitespace)
        tags = [tag.lower().strip() for tag in tags if tag.strip()]

        return tags[:5]  # Max 5 tags

    except Exception as e:
        print(f"  ⚠️  Tag suggestion failed: {e}")
        return []

def delete_all_tags(dry_run: bool = False) -> int:
    """
    Delete all tags from WordPress
    Returns the number of tags deleted
    """
    print("🗑️  Fetching existing tags...")

    try:
        # Fetch all tags
        response = requests.get(
            f"{WP_URL}/wp-json/wp/v2/tags",
            params={"per_page": 100},
            auth=wp_auth(),
            timeout=30
        )
        response.raise_for_status()

        all_tags = response.json()

        if not all_tags:
            print("   No existing tags found.\n")
            return 0

        print(f"   Found {len(all_tags)} existing tags")

        if dry_run:
            print("   [DRY RUN] Would delete these tags:")
            for tag in all_tags:
                print(f"     - {tag['name']} (ID: {tag['id']})")
            return len(all_tags)

        # Delete each tag
        deleted_count = 0
        for tag in all_tags:
            try:
                delete_response = requests.delete(
                    f"{WP_URL}/wp-json/wp/v2/tags/{tag['id']}",
                    params={"force": True},
                    auth=wp_auth(),
                    timeout=30
                )
                delete_response.raise_for_status()
                deleted_count += 1
                print(f"   ✓ Deleted: {tag['name']}")
            except Exception as e:
                print(f"   ✗ Failed to delete {tag['name']}: {e}")

        print(f"✅ Deleted {deleted_count} tags\n")
        return deleted_count

    except Exception as e:
        print(f"ERROR deleting tags: {e}\n")
        return 0

def create_tag(tag_name: str) -> int:
    """
    Create a new tag in WordPress
    Returns the tag ID
    """
    try:
        response = requests.post(
            f"{WP_URL}/wp-json/wp/v2/tags",
            json={"name": tag_name, "slug": tag_name},
            auth=wp_auth(),
            timeout=30
        )
        response.raise_for_status()
        tag_data = response.json()
        return tag_data['id']
    except Exception as e:
        print(f"   ⚠️  Failed to create tag '{tag_name}': {e}")
        return None

def update_post_tags(post_id: int, tag_ids: List[int], dry_run: bool = False) -> bool:
    """
    Update a post with new tag IDs
    """
    if dry_run:
        return True

    try:
        response = requests.post(
            f"{WP_URL}/wp-json/wp/v2/posts/{post_id}",
            json={"tags": tag_ids},
            auth=wp_auth(),
            timeout=30
        )
        response.raise_for_status()
        return True
    except Exception as e:
        print(f"   ⚠️  Failed to update post {post_id}: {e}")
        return False

def main():
    parser = argparse.ArgumentParser(
        description="Optimize WordPress article tags based on content analysis",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
This script will:
1. Delete all existing tags from WordPress
2. Analyze each article (title + first paragraph)
3. Suggest relevant tags using AI
4. Only create tags that appear in at least 10 articles
5. Apply validated tags to articles

Examples:
  # Preview changes without making them:
  python optimize_article_tags.py --dry-run

  # Actually apply the changes:
  python optimize_article_tags.py

  # Custom minimum articles per tag:
  python optimize_article_tags.py --min-articles 15
        """
    )

    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview changes without actually modifying WordPress"
    )

    parser.add_argument(
        "--min-articles",
        type=int,
        default=MIN_ARTICLES_PER_TAG,
        help=f"Minimum articles required per tag (default: {MIN_ARTICLES_PER_TAG})"
    )

    args = parser.parse_args()

    print("="*80)
    print("ARTICLE TAG OPTIMIZATION")
    if args.dry_run:
        print("[DRY RUN MODE - No changes will be made]")
    print("="*80 + "\n")

    # Step 1: Delete existing tags
    print("STEP 1: Delete existing tags")
    print("-"*80)
    deleted_count = delete_all_tags(dry_run=args.dry_run)

    # Step 2: Fetch all posts
    print("STEP 2: Fetch all articles")
    print("-"*80)
    all_posts = fetch_all_posts()

    if not all_posts:
        print("No posts found. Exiting.")
        sys.exit(1)

    # Step 3: Analyze articles and suggest tags
    print("STEP 3: Analyze articles and suggest tags")
    print("-"*80)
    print(f"Analyzing {len(all_posts)} articles...\n")

    article_tags = {}  # post_id -> [tags]
    tag_to_articles = defaultdict(list)  # tag -> [post_ids]

    for i, post in enumerate(all_posts, 1):
        title = post['title']['rendered']
        first_para = get_first_paragraph(post['content']['rendered'])

        print(f"[{i}/{len(all_posts)}] {title[:60]}...")

        suggested_tags = suggest_tags_for_article(title, first_para)

        if suggested_tags:
            print(f"   Suggested tags: {', '.join(suggested_tags)}")
            article_tags[post['id']] = suggested_tags

            # Track which articles have which tags
            for tag in suggested_tags:
                tag_to_articles[tag].append(post['id'])
        else:
            print(f"   No tags suggested")
            article_tags[post['id']] = []

    # Step 4: Filter tags by minimum article count
    print(f"\nSTEP 4: Filter tags (minimum {args.min_articles} articles per tag)")
    print("-"*80)

    valid_tags = {
        tag: articles
        for tag, articles in tag_to_articles.items()
        if len(articles) >= args.min_articles
    }

    invalid_tags = {
        tag: len(articles)
        for tag, articles in tag_to_articles.items()
        if len(articles) < args.min_articles
    }

    print(f"✅ Valid tags ({len(valid_tags)} tags):")
    for tag, articles in sorted(valid_tags.items(), key=lambda x: len(x[1]), reverse=True):
        print(f"   {tag}: {len(articles)} articles")

    if invalid_tags:
        print(f"\n❌ Rejected tags ({len(invalid_tags)} tags with < {args.min_articles} articles):")
        for tag, count in sorted(invalid_tags.items(), key=lambda x: x[1], reverse=True):
            print(f"   {tag}: {count} articles")

    # Step 5: Create valid tags and update posts
    print(f"\nSTEP 5: Apply tags to articles")
    print("-"*80)

    if args.dry_run:
        print("[DRY RUN] Would create these tags and apply to articles:")
        for tag, article_ids in sorted(valid_tags.items()):
            print(f"   Tag '{tag}' would be applied to {len(article_ids)} articles")
    else:
        # Create tags in WordPress
        print("Creating tags in WordPress...")
        tag_name_to_id = {}

        for tag_name in valid_tags.keys():
            tag_id = create_tag(tag_name)
            if tag_id:
                tag_name_to_id[tag_name] = tag_id
                print(f"   ✓ Created tag: {tag_name} (ID: {tag_id})")

        # Update posts with tags
        print(f"\nApplying tags to {len(all_posts)} articles...")

        updated_count = 0
        for post_id, suggested_tags in article_tags.items():
            # Filter to only valid tags
            valid_post_tags = [tag for tag in suggested_tags if tag in valid_tags]

            if not valid_post_tags:
                continue

            # Get tag IDs
            tag_ids = [tag_name_to_id[tag] for tag in valid_post_tags if tag in tag_name_to_id]

            if tag_ids:
                if update_post_tags(post_id, tag_ids, dry_run=False):
                    updated_count += 1
                    post_title = next((p['title']['rendered'] for p in all_posts if p['id'] == post_id), f"Post {post_id}")
                    print(f"   ✓ Updated: {post_title[:50]}... ({len(tag_ids)} tags)")

        print(f"\n✅ Updated {updated_count} articles with tags")

    # Save report
    timestamp = datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')
    report_file = f"tag_optimization_report_{timestamp}.json"

    report = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "dry_run": args.dry_run,
        "min_articles_per_tag": args.min_articles,
        "total_articles": len(all_posts),
        "tags_deleted": deleted_count,
        "valid_tags": {
            tag: len(articles)
            for tag, articles in valid_tags.items()
        },
        "rejected_tags": invalid_tags,
        "article_tags": {
            str(post_id): tags
            for post_id, tags in article_tags.items()
        }
    }

    with open(report_file, 'w', encoding='utf-8') as f:
        json.dump(report, f, indent=2, ensure_ascii=False)

    print(f"\n{'='*80}")
    print(f"💾 Full report saved to: {report_file}")
    print(f"{'='*80}\n")

    # Summary
    print("📊 SUMMARY")
    print(f"   Articles analyzed: {len(all_posts)}")
    print(f"   Valid tags created: {len(valid_tags)}")
    print(f"   Tags rejected (< {args.min_articles} articles): {len(invalid_tags)}")

    if not args.dry_run:
        print(f"\n✅ Tag optimization complete!")
    else:
        print(f"\n💡 Dry run complete. Run without --dry-run to apply changes.")

if __name__ == "__main__":
    main()
