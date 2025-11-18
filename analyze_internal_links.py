#!/usr/bin/env python3
# analyze_internal_links.py
# Analyze WordPress articles to identify internal linking opportunities

import os
import sys
import json
import re
from datetime import datetime, timezone
from typing import List, Dict, Any

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
                    "_fields": "id,title,content,link,excerpt,date,slug"
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

def analyze_internal_linking_opportunities(
    current_post: Dict[str, Any],
    all_posts: List[Dict[str, Any]]
) -> Dict[str, Any]:
    """
    Use Claude to analyze a post and suggest internal linking opportunities
    """
    # Prepare current post info
    current_title = current_post['title']['rendered']
    current_content = strip_html(current_post['content']['rendered'])
    current_url = current_post['link']

    # Prepare list of other articles (excluding current)
    other_articles = [
        {
            "title": p['title']['rendered'],
            "url": p['link'],
            "excerpt": strip_html(p['excerpt']['rendered'])[:200]
        }
        for p in all_posts
        if p['id'] != current_post['id']
    ]

    # Limit to 50 most recent for token efficiency
    other_articles = other_articles[:50]

    # Create prompt for Claude
    prompt = f"""You are an SEO specialist analyzing blog posts for internal linking opportunities.

**CURRENT ARTICLE:**
Title: {current_title}
URL: {current_url}

Content (first 2000 chars):
{current_content[:2000]}

---

**OTHER ARTICLES ON THE SITE:**
{json.dumps(other_articles, indent=2)}

---

**YOUR TASK:**
Analyze the current article and identify natural internal linking opportunities to other articles on the site.

**Guidelines:**
1. Only suggest links that are genuinely relevant and helpful to readers
2. Look for specific phrases, topics, or concepts in the current article that naturally connect to other articles
3. Suggest the exact anchor text (phrase to link) from the current article
4. Prioritize high-value links that improve user experience and SEO
5. Limit to 3-5 strongest linking opportunities (don't over-optimize)

**Return ONLY this JSON format:**

{{
  "internal_link_opportunities": [
    {{
      "anchor_text": "The exact phrase from the current article to make into a link",
      "target_article_title": "Title of the article to link to",
      "target_url": "URL of the article to link to",
      "context_snippet": "...surrounding context from current article showing where this phrase appears...",
      "relevance_reason": "Brief explanation of why this link makes sense (1 sentence)"
    }}
  ],
  "summary": "Brief 1-2 sentence summary of the linking strategy for this article"
}}

If there are NO good internal linking opportunities, return:
{{
  "internal_link_opportunities": [],
  "summary": "No strong internal linking opportunities identified."
}}
"""

    try:
        print(f"  🤖 Analyzing: {current_title[:60]}...")

        response = anthropic_client.messages.create(
            model="claude-sonnet-4-5",
            max_tokens=2000,
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

        # Try to find JSON in the response
        start = result_text.find("{")
        end = result_text.rfind("}") + 1
        if start != -1 and end > start:
            result_text = result_text[start:end]

        result = json.loads(result_text)
        return result

    except Exception as e:
        print(f"  ⚠️  Analysis failed: {e}")
        return {
            "internal_link_opportunities": [],
            "summary": f"Analysis failed: {str(e)}"
        }

def main():
    print("="*80)
    print("INTERNAL LINKING ANALYSIS")
    print("Analyzing WordPress articles for internal linking opportunities")
    print("="*80 + "\n")

    # Fetch all posts
    all_posts = fetch_all_posts()

    if not all_posts:
        print("No posts found. Exiting.")
        sys.exit(1)

    # Analyze each post
    print("🔍 Analyzing posts for internal linking opportunities...\n")

    results = []
    for i, post in enumerate(all_posts, 1):
        print(f"[{i}/{len(all_posts)}] Analyzing post...")

        analysis = analyze_internal_linking_opportunities(post, all_posts)

        results.append({
            "post_id": post['id'],
            "post_title": post['title']['rendered'],
            "post_url": post['link'],
            "analysis": analysis
        })

    # Save results
    timestamp = datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')
    output_file = f"internal_links_analysis_{timestamp}.json"

    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(results, f, indent=2, ensure_ascii=False)

    print(f"\n{'='*80}")
    print(f"💾 Full analysis saved to: {output_file}")
    print(f"{'='*80}\n")

    # Display summary
    print("📊 SUMMARY REPORT\n")
    print(f"Total articles analyzed: {len(results)}")

    total_opportunities = sum(
        len(r['analysis'].get('internal_link_opportunities', []))
        for r in results
    )
    print(f"Total internal linking opportunities found: {total_opportunities}\n")

    # Show top opportunities
    print("🔗 TOP INTERNAL LINKING OPPORTUNITIES:\n")

    for result in results:
        opportunities = result['analysis'].get('internal_link_opportunities', [])
        if opportunities:
            print(f"\n📄 {result['post_title']}")
            print(f"   URL: {result['post_url']}")
            print(f"   Strategy: {result['analysis'].get('summary', 'N/A')}")
            print(f"   Found {len(opportunities)} linking opportunities:")

            for i, opp in enumerate(opportunities, 1):
                print(f"\n   {i}. Anchor text: \"{opp['anchor_text']}\"")
                print(f"      → Link to: {opp['target_article_title']}")
                print(f"      → Target: {opp['target_url']}")
                print(f"      → Context: {opp['context_snippet'][:100]}...")
                print(f"      → Why: {opp['relevance_reason']}")

    print(f"\n{'='*80}")
    print(f"✅ Analysis complete!")
    print(f"{'='*80}\n")

    print("💡 NEXT STEPS:")
    print("1. Review the suggestions in the JSON file")
    print("2. Manually add the suggested internal links to your articles")
    print("3. Focus on the highest-value opportunities first")
    print("4. Don't over-optimize - quality over quantity\n")

if __name__ == "__main__":
    main()
