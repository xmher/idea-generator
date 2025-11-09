# RSS Feed Sources - Quick Reference

## 📦 Installation

```bash
pip install feedparser
```

## 🎯 High-Priority Feeds (8 total)

### Media Accountability & Performance
1. **AdExchanger** - https://adexchanger.com/feed/
2. **AdAge** - https://adage.com/rss-feed
3. **Digiday** - https://digiday.com/feed/

### Advertising Strategy & Investment
4. **The Drum** - https://www.thedrum.com/rss/news/all
5. **MediaPost - Agency Daily** - https://www.mediapost.com/publications/rss/agency-daily.xml
6. **Search Engine Land** - https://searchengineland.com/feed

### Media Analysis, AI & Automation
7. **MarTech** - https://martech.org/feed/
8. **MediaPost - Data & Targeting** - https://www.mediapost.com/publications/rss/data-and-targeting-insider.xml

## 🚀 Quick Test

```bash
# Test the RSS fetcher
python rss_fetcher.py

# Fetch only last 24 hours
python rss_fetcher.py --max-age 24

# See all feeds (including medium priority)
python rss_fetcher.py --all
```

## 📊 All Feeds (14 total)

**Pillar 1: Media Accountability & Performance** (5 feeds)
- AdExchanger (high priority)
- AdAge - News (high priority)
- Digiday (high priority)
- MediaPost - Online Media Daily (medium priority)
- MediaPost - Research (medium priority)

**Pillar 2: Advertising Strategy & Investment** (5 feeds)
- The Drum (high priority)
- MediaPost - Agency Daily (high priority)
- Search Engine Land (high priority)
- MediaPost - Marketing Daily (medium priority)
- AdAge - Brand Marketing (medium priority)

**Pillar 3: Media Analysis, AI & Automation** (4 feeds)
- MarTech (high priority)
- MediaPost - Data & Targeting Insider (high priority)
- MediaPost - Social Media Daily (medium priority)
- MediaPost - Mobile Marketing Daily (medium priority)

## 💡 Why These Feeds?

✅ **Industry Authority** - Established B2B publications
✅ **Professional Focus** - For practitioners, not consumers
✅ **Pillar Aligned** - Maps to your 3 content pillars
✅ **No Auth Required** - All feeds are publicly accessible
✅ **Regular Updates** - Daily publishing schedules

## 🔗 See Also

- **RSS_INTEGRATION_GUIDE.md** - Full integration instructions
- **rss_sources.py** - Source configuration (customize here)
- **rss_fetcher.py** - Fetching utilities
