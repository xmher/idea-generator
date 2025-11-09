#!/usr/bin/env python3
"""
RSS Feed Fetcher for Melissa E-E-A-T Idea Factory
Fetches and parses RSS feeds from industry publications
"""

import logging
from datetime import datetime, timezone, timedelta
from typing import List, Dict, Any, Optional
from urllib.parse import urlparse
import hashlib

try:
    import feedparser
except ImportError:
    print("FATAL: Missing 'feedparser' library. Install with 'pip install feedparser'.")
    raise SystemExit(1)

from rss_sources import ALL_RSS_FEEDS, HIGH_PRIORITY_FEEDS, RSS_CONFIG

log = logging.getLogger("rss-fetcher")

# ============================================================================
# RSS ENTRY DATA CLASS
# ============================================================================

class RSSEntry:
    """Represents a single RSS feed entry"""

    def __init__(self, entry: dict, feed_info: dict):
        self.title = entry.get("title", "").strip()
        self.link = entry.get("link", "").strip()
        self.summary = entry.get("summary", "").strip()
        self.published = self._parse_date(entry)
        self.source = feed_info["name"]
        self.pillar = feed_info["pillar"]
        self.topics = feed_info.get("topics", [])

        # Generate unique ID
        self.id = self._generate_id()

    def _parse_date(self, entry: dict) -> Optional[datetime]:
        """Parse published date from entry"""
        if hasattr(entry, "published_parsed") and entry.published_parsed:
            try:
                return datetime(*entry.published_parsed[:6], tzinfo=timezone.utc)
            except Exception:
                pass
        return None

    def _generate_id(self) -> str:
        """Generate unique ID from URL or title"""
        unique_str = self.link or self.title
        return hashlib.md5(unique_str.encode()).hexdigest()[:16]

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "id": self.id,
            "title": self.title,
            "url": self.link,
            "summary": self.summary,
            "published": self.published.isoformat() if self.published else None,
            "source": self.source,
            "pillar": self.pillar,
            "topics": self.topics,
        }

    def __repr__(self):
        return f"<RSSEntry: {self.source} - {self.title[:50]}...>"


# ============================================================================
# RSS FETCHER
# ============================================================================

def fetch_rss_feed(feed_info: Dict[str, Any], max_entries: int = None) -> List[RSSEntry]:
    """
    Fetch and parse a single RSS feed

    Args:
        feed_info: Dictionary with feed configuration (url, name, pillar, etc.)
        max_entries: Maximum number of entries to return (None = all)

    Returns:
        List of RSSEntry objects
    """
    url = feed_info["url"]
    max_entries = max_entries or RSS_CONFIG["max_entries_per_feed"]

    log.info(f"Fetching RSS feed: {feed_info['name']} ({url})")

    try:
        # Parse the feed
        feed = feedparser.parse(url)

        # Check for errors
        if feed.bozo:
            log.warning(f"Feed parsing warning for {feed_info['name']}: {feed.bozo_exception}")

        # Extract entries
        entries = []
        for entry in feed.entries[:max_entries]:
            try:
                rss_entry = RSSEntry(entry, feed_info)
                entries.append(rss_entry)
            except Exception as e:
                log.warning(f"Error parsing entry from {feed_info['name']}: {e}")
                continue

        log.info(f"✓ Fetched {len(entries)} entries from {feed_info['name']}")
        return entries

    except Exception as e:
        log.error(f"Failed to fetch feed {feed_info['name']}: {e}")
        return []


def fetch_all_feeds(feeds: List[Dict[str, Any]] = None,
                   max_age_hours: int = None) -> List[RSSEntry]:
    """
    Fetch all RSS feeds (or specified list)

    Args:
        feeds: List of feed configurations (None = use HIGH_PRIORITY_FEEDS)
        max_age_hours: Only return entries newer than this (None = use config default)

    Returns:
        List of all RSSEntry objects
    """
    feeds = feeds or HIGH_PRIORITY_FEEDS
    max_age_hours = max_age_hours or RSS_CONFIG["max_age_hours"]

    cutoff_time = datetime.now(timezone.utc) - timedelta(hours=max_age_hours)

    all_entries = []
    for feed_info in feeds:
        entries = fetch_rss_feed(feed_info)
        all_entries.extend(entries)

    # Filter by age
    recent_entries = [
        entry for entry in all_entries
        if entry.published is None or entry.published >= cutoff_time
    ]

    log.info(f"Total entries fetched: {len(all_entries)}, "
             f"recent (within {max_age_hours}h): {len(recent_entries)}")

    return recent_entries


def deduplicate_entries(entries: List[RSSEntry]) -> List[RSSEntry]:
    """
    Remove duplicate entries based on URL and title similarity

    Args:
        entries: List of RSSEntry objects

    Returns:
        Deduplicated list
    """
    if not RSS_CONFIG.get("dedupe_by_url"):
        return entries

    seen_urls = set()
    seen_titles = set()
    unique_entries = []

    for entry in entries:
        # Dedupe by URL
        if RSS_CONFIG.get("dedupe_by_url") and entry.link:
            if entry.link in seen_urls:
                log.debug(f"Skipping duplicate URL: {entry.link}")
                continue
            seen_urls.add(entry.link)

        # Dedupe by title (normalize and compare)
        if RSS_CONFIG.get("dedupe_by_title"):
            normalized_title = entry.title.lower().strip()
            if normalized_title in seen_titles:
                log.debug(f"Skipping duplicate title: {entry.title}")
                continue
            seen_titles.add(normalized_title)

        unique_entries.append(entry)

    log.info(f"Deduplication: {len(entries)} -> {len(unique_entries)} entries")
    return unique_entries


def rank_entries_by_recency(entries: List[RSSEntry]) -> List[RSSEntry]:
    """
    Sort entries by published date (most recent first)

    Args:
        entries: List of RSSEntry objects

    Returns:
        Sorted list
    """
    # Entries without published date go to the end
    return sorted(
        entries,
        key=lambda e: e.published or datetime.min.replace(tzinfo=timezone.utc),
        reverse=True
    )


def get_rss_candidates(use_high_priority_only: bool = True,
                      max_age_hours: int = None,
                      max_total: int = 50) -> List[Dict[str, Any]]:
    """
    Main entry point: Fetch, deduplicate, and rank RSS entries

    Args:
        use_high_priority_only: Only fetch high-priority feeds
        max_age_hours: Maximum age of entries to consider
        max_total: Maximum total entries to return

    Returns:
        List of dictionaries ready for pipeline processing
    """
    log.info("="*80)
    log.info("Fetching RSS Feed Candidates")
    log.info("="*80)

    # Select feeds
    feeds = HIGH_PRIORITY_FEEDS if use_high_priority_only else ALL_RSS_FEEDS
    log.info(f"Using {len(feeds)} feeds (high priority only: {use_high_priority_only})")

    # Fetch all entries
    entries = fetch_all_feeds(feeds, max_age_hours)

    # Deduplicate
    entries = deduplicate_entries(entries)

    # Rank by recency
    entries = rank_entries_by_recency(entries)

    # Limit total
    entries = entries[:max_total]

    log.info(f"Returning {len(entries)} RSS candidates for processing")

    # Convert to dictionaries
    return [entry.to_dict() for entry in entries]


# ============================================================================
# CLI FOR TESTING
# ============================================================================

if __name__ == "__main__":
    import argparse

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)s | %(message)s"
    )

    parser = argparse.ArgumentParser(description="Test RSS Feed Fetcher")
    parser.add_argument("--all", action="store_true", help="Fetch all feeds (not just high priority)")
    parser.add_argument("--max-age", type=int, default=48, help="Max age in hours (default: 48)")
    parser.add_argument("--limit", type=int, default=50, help="Max total entries (default: 50)")

    args = parser.parse_args()

    candidates = get_rss_candidates(
        use_high_priority_only=not args.all,
        max_age_hours=args.max_age,
        max_total=args.limit
    )

    print("\n" + "="*80)
    print(f"RSS CANDIDATES ({len(candidates)} total)")
    print("="*80)

    for i, entry in enumerate(candidates[:10], 1):  # Show first 10
        print(f"\n{i}. [{entry['source']}] {entry['title']}")
        print(f"   URL: {entry['url']}")
        print(f"   Pillar: {entry['pillar']}")
        if entry['published']:
            print(f"   Published: {entry['published']}")

    if len(candidates) > 10:
        print(f"\n... and {len(candidates) - 10} more entries")
