# RSS Feed Integration Guide

This guide explains how to use RSS feeds as an additional source for your idea generator.

## 📦 Setup

### 1. Install Required Dependency

```bash
pip install feedparser
```

### 2. Files Added

- **`rss_sources.py`** - Curated RSS feed sources organized by pillar
- **`rss_fetcher.py`** - RSS parsing and fetching utilities
- **`RSS_INTEGRATION_GUIDE.md`** - This guide

## 📊 Available RSS Feeds

### Pillar 1: Media Accountability & Performance
- **AdExchanger** - Programmatic advertising and ad tech news
- **AdAge** - Advertising industry news and campaigns
- **Digiday** - Digital advertising and media news
- **MediaPost** - Online media and research insights

### Pillar 2: Advertising Strategy & Investment
- **The Drum** - Marketing strategy and creative news
- **Search Engine Land** - SEO, PPC, and search marketing
- **MediaPost - Agency Daily** - Agency news and industry moves

### Pillar 3: Media Analysis, AI & Automation
- **MarTech** - Marketing technology and AI news
- **MediaPost - Data & Targeting** - Analytics and automation

**Total:** 14+ curated RSS feeds (9 high-priority)

## 🚀 Quick Start

### Test the RSS Fetcher

```bash
# Fetch high-priority feeds (default)
python rss_fetcher.py

# Fetch ALL feeds
python rss_fetcher.py --all

# Fetch only posts from last 24 hours
python rss_fetcher.py --max-age 24

# Limit to 20 entries
python rss_fetcher.py --limit 20
```

### Use in Your Pipeline

#### Option 1: Standalone RSS Mode

Run your existing script with RSS URLs instead of topics:

```bash
# Pick an RSS entry URL from the fetcher output
python main.py "https://adexchanger.com/example-article/"
```

#### Option 2: Integrate into Auto-Discovery

Add RSS fetching alongside Reddit discovery. Here's how to modify `main.py`:

```python
# At the top of main.py, add:
from rss_fetcher import get_rss_candidates

# In the main() function, in AUTO-DISCOVERY mode:
def main():
    # ... existing code ...

    if not args.topic_or_url:
        log.info("--- Running in AUTO-DISCOVERY mode ---")

        # 1. Fetch Reddit candidates (existing)
        reddit_candidates = fetch_and_filter_reddit_candidates()

        # 2. Fetch RSS candidates (NEW!)
        rss_candidates = get_rss_candidates(
            use_high_priority_only=True,  # Only high-priority feeds
            max_age_hours=24,              # Last 24 hours
            max_total=30                   # Max 30 entries
        )

        # 3. Convert RSS entries to same format as Reddit posts
        for rss_entry in rss_candidates:
            # Run relevance filter on RSS entries
            filter_result = agent_relevance_filter(rss_entry["title"])
            if filter_result:
                # Add to candidates with ranking
                rss_entry.update(filter_result)
                ai_relevance = rss_entry.get("relevance_score", 0.0)
                rss_entry["ranking_score"] = ai_relevance  # Pure AI score for RSS
                reddit_candidates.append({
                    "id": rss_entry["id"],
                    "title": rss_entry["title"],
                    "url": rss_entry["url"],
                    "score": 0,  # RSS doesn't have Reddit score
                    "subreddit": rss_entry["source"],  # Use RSS source as "subreddit"
                    "ranking_score": rss_entry["ranking_score"],
                    "relevance_score": ai_relevance,
                    "reason": filter_result.get("reason")
                })

        # 4. Continue with existing selection logic
        if not reddit_candidates:
            log.info("No candidates from Reddit or RSS. Exiting.")
            return

        # ... rest of existing code ...
```

## ⚙️ Configuration

### Customize Feed Selection

Edit `rss_sources.py` to:

1. **Add/Remove Feeds**
   ```python
   RSS_FEEDS["Your Pillar Name"].append({
       "name": "New Feed",
       "url": "https://example.com/feed/",
       "description": "Description",
       "priority": "high",
       "topics": ["topic1", "topic2"]
   })
   ```

2. **Change Priority Levels**
   - `"high"` - Fetched by default
   - `"medium"` - Fetched when using `--all` flag
   - `"low"` - Background/reference feeds

3. **Adjust Fetch Settings**
   ```python
   RSS_CONFIG = {
       "max_entries_per_feed": 20,   # Entries per feed
       "max_age_hours": 48,           # Only posts from last 48h
       "dedupe_by_url": True,         # Remove duplicate URLs
       "dedupe_by_title": True,       # Remove similar titles
   }
   ```

## 🔍 RSS Feed Details

### Why These Feeds?

All feeds are selected to align with Melissa's "trifecta" expertise:

1. **Industry Authority** - Established publications (AdAge, AdExchanger, Digiday)
2. **Professional Focus** - B2B content for practitioners, not consumers
3. **Pillar Alignment** - Each feed maps to at least one content pillar
4. **Insider Depth** - Sources go beyond press releases

### Feed Reliability

All feeds are from established publications with:
- ✅ Regular publishing schedules
- ✅ Professional editorial standards
- ✅ Valid RSS 2.0 or Atom format
- ✅ No authentication required

## 📝 Example Workflow

### Combined Reddit + RSS Pipeline

```bash
# 1. Test RSS fetcher first
python rss_fetcher.py --max-age 24 --limit 20

# 2. Review the candidates (manually or via the output)

# 3. Run the full pipeline in auto-discovery mode
# (After integrating RSS into main.py as shown above)
python main.py

# This will:
# - Fetch Reddit posts (existing)
# - Fetch RSS entries (new)
# - Run AI relevance filter on both
# - Rank and select best candidates
# - Generate idea stubs for top items
```

### RSS-Only Mode (Manual)

```bash
# 1. Find an interesting article
python rss_fetcher.py | grep "AdExchanger"

# 2. Run idea generator on that URL
python main.py "https://adexchanger.com/interesting-article/"
```

## 🎯 Benefits of RSS Integration

1. **Broader Coverage** - Professional publications beyond Reddit
2. **Higher Quality** - Curated, editorial content
3. **Less Noise** - Pre-filtered by publication standards
4. **Pillar Alignment** - Feeds organized by your content pillars
5. **Diversified Sources** - Mix of ad tech, strategy, and analysis

## 🛠️ Troubleshooting

### "Missing feedparser library"
```bash
pip install feedparser
```

### "Feed parsing warning"
- Some feeds may have minor formatting issues
- The parser will still extract entries successfully
- Check logs for specific warnings

### No Entries Returned
- Check `max_age_hours` setting (default: 48h)
- Try `--all` flag to fetch all priority levels
- Verify feed URLs are still active

## 📈 Next Steps

1. **Test the fetcher** with `python rss_fetcher.py`
2. **Review the candidates** to verify quality
3. **Integrate into main.py** using Option 2 above
4. **Adjust feed priorities** based on your content needs
5. **Add custom feeds** for niche topics

## 💡 Tips

- Start with **high-priority feeds only** to avoid overwhelming the pipeline
- Use **max_age_hours=24** for daily runs, **48** for every-other-day
- RSS entries work great with your existing relevance filter
- RSS provides more "evergreen" analysis vs. Reddit's trending topics
- Combine both sources for maximum coverage and diversity

---

**Questions?** Test the RSS fetcher first to see it in action, then integrate gradually into your existing pipeline.
