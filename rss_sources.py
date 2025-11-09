# rss_sources.py
# RSS Feed Sources for Melissa E-E-A-T Idea Factory
# Organized by the Three Content Pillars

"""
RSS Feed Sources Configuration

This file contains curated RSS feeds from industry publications aligned with
the three content pillars. These feeds provide professional, insider-focused
content for the advertising & media analysis blog.
"""

# ============================================================================
# RSS FEED SOURCES (Organized by Pillar)
# ============================================================================

RSS_FEEDS = {
    # ------------------------------------------------------------------------
    # PILLAR 1: Media Accountability & Performance (Auditor Lens)
    # Focus: Ad performance, measurement, fraud, verification, audit
    # ------------------------------------------------------------------------
    "Media Accountability & Performance": [
        {
            "name": "AdExchanger",
            "url": "https://adexchanger.com/feed/",
            "description": "Programmatic advertising, ad tech, data-driven marketing ecosystem",
            "priority": "high",  # high, medium, low
            "topics": ["programmatic", "ad tech", "measurement", "data privacy"]
        },
        {
            "name": "AdAge - News",
            "url": "https://adage.com/rss-feed",
            "description": "Advertising industry news, campaigns, media analysis",
            "priority": "high",
            "topics": ["advertising news", "campaigns", "media buying"]
        },
        {
            "name": "Digiday",
            "url": "https://digiday.com/feed/",
            "description": "Digital advertising, marketing, and media news",
            "priority": "high",
            "topics": ["digital advertising", "media", "publishing"]
        },
        {
            "name": "MediaPost - Online Media Daily",
            "url": "https://www.mediapost.com/publications/rss/online-media-daily.xml",
            "description": "Online media and advertising news",
            "priority": "medium",
            "topics": ["online media", "digital advertising"]
        },
        {
            "name": "MediaPost - Research",
            "url": "https://www.mediapost.com/publications/rss/research.xml",
            "description": "Marketing and advertising research insights",
            "priority": "medium",
            "topics": ["research", "data", "industry insights"]
        },
    ],

    # ------------------------------------------------------------------------
    # PILLAR 2: Advertising Strategy & Investment (Agency Lens)
    # Focus: Client strategy, media investment, agency business, pitches
    # ------------------------------------------------------------------------
    "Advertising Strategy & Investment": [
        {
            "name": "The Drum",
            "url": "https://www.thedrum.com/rss/news/all",
            "description": "Marketing and advertising industry news, strategy, creative",
            "priority": "high",
            "topics": ["marketing strategy", "agencies", "creative", "campaigns"]
        },
        {
            "name": "MediaPost - Agency Daily",
            "url": "https://www.mediapost.com/publications/rss/agency-daily.xml",
            "description": "Agency news, pitches, and industry moves",
            "priority": "high",
            "topics": ["agencies", "industry news", "business"]
        },
        {
            "name": "MediaPost - Marketing Daily",
            "url": "https://www.mediapost.com/publications/rss/marketing-daily.xml",
            "description": "Marketing strategy and brand news",
            "priority": "medium",
            "topics": ["marketing", "brands", "strategy"]
        },
        {
            "name": "Search Engine Land",
            "url": "https://searchengineland.com/feed",
            "description": "SEO, PPC, SEM news and strategy",
            "priority": "high",
            "topics": ["PPC", "SEO", "search marketing", "Google Ads"]
        },
        {
            "name": "AdAge - Brand Marketing",
            "url": "https://adage.com/section/brand-marketing/rss",
            "description": "Brand marketing strategies and campaigns",
            "priority": "medium",
            "topics": ["brand marketing", "strategy", "CMO"]
        },
    ],

    # ------------------------------------------------------------------------
    # PILLAR 3: Media Analysis, AI & Automation (In-House Lens)
    # Focus: AI tools, automation, in-house analytics, martech
    # ------------------------------------------------------------------------
    "Media Analysis, AI & Automation": [
        {
            "name": "MarTech",
            "url": "https://martech.org/feed/",
            "description": "Marketing technology news, AI, automation, analytics",
            "priority": "high",
            "topics": ["martech", "AI", "automation", "analytics"]
        },
        {
            "name": "MediaPost - Data & Targeting Insider",
            "url": "https://www.mediapost.com/publications/rss/data-and-targeting-insider.xml",
            "description": "Data analytics, targeting, and tech insights",
            "priority": "high",
            "topics": ["data", "targeting", "analytics", "automation"]
        },
        {
            "name": "MediaPost - Social Media & Marketing Daily",
            "url": "https://www.mediapost.com/publications/rss/social-media-marketing-daily.xml",
            "description": "Social media marketing news and analytics",
            "priority": "medium",
            "topics": ["social media", "platforms", "sentiment analysis"]
        },
        {
            "name": "MediaPost - Mobile Marketing Daily",
            "url": "https://www.mediapost.com/publications/rss/mobile-marketing-daily.xml",
            "description": "Mobile marketing and app advertising",
            "priority": "medium",
            "topics": ["mobile", "apps", "in-app advertising"]
        },
    ],
}

# ============================================================================
# FLATTENED FEED LIST (for easy iteration)
# ============================================================================

ALL_RSS_FEEDS = []
for pillar, feeds in RSS_FEEDS.items():
    for feed in feeds:
        ALL_RSS_FEEDS.append({
            **feed,
            "pillar": pillar
        })

# ============================================================================
# HIGH PRIORITY FEEDS ONLY
# ============================================================================

HIGH_PRIORITY_FEEDS = [
    feed for feed in ALL_RSS_FEEDS
    if feed.get("priority") == "high"
]

# ============================================================================
# RSS FETCH CONFIGURATION
# ============================================================================

RSS_CONFIG = {
    "max_entries_per_feed": 20,  # How many recent entries to fetch per feed
    "fetch_interval_hours": 6,   # How often to check feeds (for scheduled runs)
    "min_age_hours": 0,          # Minimum age of posts to consider (0 = all recent)
    "max_age_hours": 48,         # Maximum age of posts to consider (48 = last 2 days)
    "dedupe_by_url": True,       # Remove duplicate posts by URL
    "dedupe_by_title": True,     # Remove duplicate posts by similar title
}

# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def get_feeds_by_pillar(pillar_name: str) -> list:
    """Get all feeds for a specific pillar"""
    return RSS_FEEDS.get(pillar_name, [])

def get_feeds_by_priority(priority: str) -> list:
    """Get all feeds with a specific priority level"""
    return [feed for feed in ALL_RSS_FEEDS if feed.get("priority") == priority]

def get_feed_by_name(feed_name: str) -> dict:
    """Get a specific feed by name"""
    for feed in ALL_RSS_FEEDS:
        if feed["name"] == feed_name:
            return feed
    return None

# ============================================================================
# USAGE EXAMPLES
# ============================================================================

if __name__ == "__main__":
    print(f"Total RSS Feeds: {len(ALL_RSS_FEEDS)}")
    print(f"High Priority Feeds: {len(HIGH_PRIORITY_FEEDS)}")
    print("\nFeeds by Pillar:")
    for pillar, feeds in RSS_FEEDS.items():
        print(f"  {pillar}: {len(feeds)} feeds")

    print("\n" + "="*80)
    print("HIGH PRIORITY FEEDS:")
    print("="*80)
    for feed in HIGH_PRIORITY_FEEDS:
        print(f"\n[{feed['pillar']}]")
        print(f"  Name: {feed['name']}")
        print(f"  URL: {feed['url']}")
        print(f"  Topics: {', '.join(feed['topics'])}")
