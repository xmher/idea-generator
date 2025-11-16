# Social Media Post Generator Guide

Automatically generate Threads and Twitter posts from your articles with AI-powered content and optional Canva template integration.

## 📁 Files Overview

- **`social_prompts.py`** - AI prompts for both platforms and both streams
- **`generate_threads_post.py`** - Generate Threads posts (text-only)
- **`generate_twitter_post.py`** - Generate Twitter posts with Canva integration
- **`canva_helper.py`** - Canva API helper functions

## 🚀 Quick Start

### 1. Install Dependencies

```bash
# Already installed if you're using the idea generator:
# - anthropic
# - python-dotenv
# - requests
```

### 2. Set Up Environment Variables

Add to your `.env` file:

```bash
# Required for post generation
ANTHROPIC_API_KEY=your_anthropic_key_here

# Optional - only needed for automatic Canva template updates
CANVA_API_KEY=your_canva_api_key_here
```

**Getting a Canva API Key:**
1. Go to https://www.canva.com/developers/
2. Create a developer account or log in
3. Create a new app/integration
4. Copy your API key

### 3. Prepare Your Canva Template (Twitter Only)

For Twitter posts to automatically update Canva templates, you need:

1. **Create a template in Canva** with text placeholders
2. **Name your text elements** (important!):
   - For **Advertising**: Name elements "Headline" and "Stat"
   - For **Romantasy**: Name elements "Headline" and "Subtext"
3. **Get your template ID** from the Canva URL:
   - URL format: `https://www.canva.com/design/ABC123XYZ/...`
   - Template ID: `ABC123XYZ`

**Customizing Element Names:**

If you want different element names in your template, edit `generate_twitter_post.py`:

```python
# Around line 100-109
if stream == "advertising":
    element_mapping = {
        "canva_headline": "YOUR_ELEMENT_NAME_HERE",  # Change this
        "canva_stat": "YOUR_STAT_ELEMENT_NAME"       # Change this
    }
```

## 📱 Usage

### Threads Posts

#### Interactive Mode (Recommended)
```bash
python generate_threads_post.py --stream advertising
# Then paste your article text and press Ctrl+D
```

#### From File
```bash
cat article.txt | python generate_threads_post.py --stream romantasy
```

#### Direct Text
```bash
python generate_threads_post.py --stream advertising --text "Your article text here..."
```

#### Save to Specific File
```bash
python generate_threads_post.py --stream advertising --output my_thread.txt
```

**Output:**
- Prints the Threads post(s) to console
- Auto-saves to `threads_post_{stream}_{timestamp}.txt`
- Can create multi-post threads when needed

---

### Twitter Posts

#### Interactive Mode (Recommended)
```bash
python generate_twitter_post.py --stream advertising
# Then paste your article text and press Ctrl+D
```

#### With Canva Template Update
```bash
python generate_twitter_post.py --stream advertising --canva-design YOUR_TEMPLATE_ID
```

#### From File
```bash
cat article.txt | python generate_twitter_post.py --stream romantasy --canva-design ABC123
```

#### Direct Text with Canva
```bash
python generate_twitter_post.py \
  --stream advertising \
  --text "Your article here..." \
  --canva-design YOUR_TEMPLATE_ID
```

**Output:**
- Prints tweet text and Canva template text to console
- Auto-saves to `twitter_post_{stream}_{timestamp}.json`
- If Canva integration is enabled:
  - Creates a duplicate of your template
  - Updates text elements
  - Exports as PNG
  - Provides edit URL and download URL

---

## 🎨 Canva Integration Details

### How It Works

1. **Duplicate**: Creates a copy of your template (preserves original)
2. **Update**: Fills in text placeholders with generated content
3. **Export**: Exports the updated design as PNG
4. **Return**: Provides edit URL and download link

### Workflow Example

```bash
# Generate Twitter post with Canva update
python generate_twitter_post.py \
  --stream advertising \
  --canva-design DAGBxyz123

# Output:
🐦 TWITTER POST (ADVERTISING)
============================================================

📱 TWEET TEXT:
------------------------------------------------------------
AI ad spend hit $50B in 2024

But 67% of marketers can't prove ROI.

The hype train is crashing. Finally.
------------------------------------------------------------
Character count: 98

🎨 CANVA TEMPLATE TEXT:
------------------------------------------------------------
Headline: AI Ad Spend Hits $50B
Stat: 67% Can't Prove ROI
------------------------------------------------------------

🎨 UPDATING CANVA TEMPLATE...
1. Duplicating template DAGBxyz123...
2. Updating text in design NEW_ID_HERE...
   - Headline: AI Ad Spend Hits $50B
   - Stat: 67% Can't Prove ROI
3. Exporting as png...
✅ Template updated! Edit at: https://canva.com/design/NEW_ID/edit
   Download: https://canva.com/export/NEW_ID/download.png

💾 Saved to: twitter_post_advertising_20250116_143022.json
```

### Without Canva API Key

If `CANVA_API_KEY` is not set, the script still works:

```bash
python generate_twitter_post.py --stream advertising

# Output shows what to manually update:
⚠️  Canva API key not configured. Update template manually.

Headline: AI Ad Spend Hits $50B
Stat: 67% Can't Prove ROI
```

Just copy these values into your Canva template manually.

---

## 🎯 Platform-Specific Guidelines

### Threads

**The Viral Edit (Advertising):**
- Witty, data-driven tone
- Lead with surprising facts/stats
- Skeptical industry humor
- 500 chars max per post
- Can create threads for deeper analysis

**Plot Brew (Romantasy):**
- Personal, vulnerable tone
- Community-focused ("we" language)
- Celebrate the genre
- Use emojis ✨💫📚
- Lead with relatable struggles

### Twitter/X

**The Viral Edit (Advertising):**
- Punchy, front-loaded hook
- Data/stats in first line
- 240-260 characters (leaves room for link)
- Works with visual Canva template
- Numbers and percentages

**Plot Brew (Romantasy):**
- Emotional, relatable hook
- Community language
- 240-260 characters
- 2-3 thematic emojis
- Craft/trope focused

---

## 🔧 Troubleshooting

### "ANTHROPIC_API_KEY not found"
- Add `ANTHROPIC_API_KEY` to your `.env` file
- Or set it in your shell: `export ANTHROPIC_API_KEY=your_key`

### "No article text provided"
- Make sure to paste text and press `Ctrl+D` to finish input
- Or use `--text "..."` flag
- Or pipe from file: `cat file.txt | python ...`

### Canva: "element not found"
- Check that your template has text elements
- Make sure element names match exactly (case-sensitive)
- Edit `generate_twitter_post.py` to customize element mapping

### Canva: "403 Forbidden" or "401 Unauthorized"
- Check that `CANVA_API_KEY` is correct
- Verify your Canva API app has necessary permissions
- Ensure template is accessible with your API credentials

### JSON parsing error
- The AI sometimes returns non-JSON for Twitter posts
- Script tries to extract JSON from markdown blocks
- If it fails, try running again or check the error output

---

## 📊 Customization

### Modify AI Prompts

Edit `social_prompts.py` to change:
- Tone and voice
- Post structure
- Platform best practices
- Content priorities

### Adjust Character Limits

Twitter prompts ask for 240-260 chars. Edit in `social_prompts.py`:

```python
# Change this line:
- 280 characters MAX (aim for 240-260 to leave room for link)

# To whatever you prefer:
- 280 characters MAX (aim for 220-240 to leave room for link)
```

### Add New Streams

To add a third blog stream (e.g., "fitness"):

1. Add prompts in `social_prompts.py`:
   ```python
   THREADS_FITNESS_PROMPT = """..."""
   TWITTER_FITNESS_PROMPT = """..."""
   ```

2. Update both generator scripts:
   ```python
   parser.add_argument(
       "--stream",
       choices=["advertising", "romantasy", "fitness"],  # Add here
       ...
   )
   ```

3. Add conditional logic in generation functions

---

## 💡 Tips & Best Practices

### For Best Results

1. **Paste complete articles**: Include headline, body, data/stats
2. **Include context**: Add relevant quotes, numbers, sources
3. **Review before posting**: AI is good but not perfect
4. **Test Canva templates**: Run once manually to verify element names

### Workflow Recommendation

1. Write article in your editor
2. Copy full text
3. Run generator (Threads + Twitter)
4. Review generated posts
5. Make minor edits if needed
6. Post Threads first (easier, no image)
7. Use Canva-generated image for Twitter
8. Schedule or post immediately

### Automation Ideas

Create bash scripts for common workflows:

```bash
#!/bin/bash
# generate_social.sh

ARTICLE_FILE=$1
STREAM=$2
CANVA_ID=$3

echo "Generating Threads post..."
cat "$ARTICLE_FILE" | python generate_threads_post.py --stream "$STREAM"

echo ""
echo "Generating Twitter post..."
cat "$ARTICLE_FILE" | python generate_twitter_post.py \
  --stream "$STREAM" \
  --canva-design "$CANVA_ID"
```

Usage:
```bash
chmod +x generate_social.sh
./generate_social.sh article.txt advertising YOUR_TEMPLATE_ID
```

---

## 🆘 Support

- Check the `--help` flag on each script
- Review error messages (they're usually specific)
- Test Canva API connection: `python canva_helper.py`
- Verify API keys in `.env`

---

## 📝 Examples

See the `/examples` directory (if created) for sample inputs and outputs.

Or run with test text:

```bash
echo "AI is transforming advertising. But is it working? New data shows 67% of marketers can't prove ROI on AI tools, despite spending $50B in 2024. The hype is crashing." | python generate_threads_post.py --stream advertising
```
