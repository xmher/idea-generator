# Social Media Post Generator Guide

Automatically generate Threads and Twitter posts from your articles with AI-powered content.

## 📁 Files Overview

- **`social_prompts.py`** - AI prompts for both platforms and both streams
- **`generate_threads_post.py`** - Generate Threads posts (text-only)
- **`generate_twitter_post.py`** - Generate Twitter posts + design template text

## 🚀 Quick Start

### 1. Install Dependencies

```bash
# Already installed if you're using the idea generator:
# - anthropic
# - python-dotenv
```

### 2. Set Up Environment Variables

Add to your `.env` file:

```bash
# Required for post generation
ANTHROPIC_API_KEY=your_anthropic_key_here
```

That's it! No other setup needed.

### 3. Your Workflow

These scripts generate optimized text for both platforms. You then copy/paste into your design tool of choice.

**Simple 3-step process:**
1. Run the script and paste your article
2. Copy the generated text
3. Paste into your design tool (Canva, Figma, Bannerbear, etc.)

**Total time: ~30 seconds**

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

#### From File
```bash
cat article.txt | python generate_twitter_post.py --stream romantasy
```

#### Direct Text
```bash
python generate_twitter_post.py --stream advertising --text "Your article here..."
```

#### Save to Specific File
```bash
python generate_twitter_post.py --stream advertising --output my_tweet.json
```

**Output:**
- Tweet text (ready to post)
- Design template text (headline, stat/subtext)
- Auto-saves to `twitter_post_{stream}_{timestamp}.json`

**Example output:**
```
🐦 TWITTER POST (ADVERTISING)
============================================================

📱 TWEET TEXT:
------------------------------------------------------------
AI ad spend hit $50B in 2024

But 67% of marketers can't prove ROI.

The hype train is crashing.
------------------------------------------------------------
Character count: 98

🎨 DESIGN TEMPLATE TEXT:
------------------------------------------------------------
Headline: AI Ad Spend Hits $50B
Stat: 67% Can't Prove ROI
------------------------------------------------------------

💡 Copy these values into your design tool (Canva, Figma, Bannerbear, etc.)
```

---

## 🎨 Using with Design Tools

The scripts generate text that works with **any design tool**:

### **Canva**
1. Create a template with text elements for "Headline" and "Stat" (or "Subtext")
2. Run the script to generate text
3. Copy/paste the values into your template
4. Export and post

### **Figma**
Same process - create text layers and paste the generated values

### **Bannerbear, Placid, or other design APIs**
If you want full automation with a design API tool, these have simple API key authentication (unlike Canva's OAuth). The scripts can be extended to integrate with these tools.

### **No Design Tool?**
Just post the tweet text alone - Twitter works fine with text-only posts too!

**Recommended workflow:**
- Create one template in your preferred tool
- Save it as a master
- Each time you run the script, duplicate the master and update the text
- Takes ~30 seconds

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
- Pairs with design template (headline + stat)
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
4. **Keep a master template**: Create one design template and duplicate for each post

### Workflow Recommendation

1. Write article in your editor
2. Copy full text
3. Run generator (Threads + Twitter)
4. Review generated posts
5. Make minor edits if needed
6. Post Threads first (easier, text-only)
7. Copy template text into your design tool for Twitter
8. Export image and post

### Automation Ideas

Create bash scripts for common workflows:

```bash
#!/bin/bash
# generate_social.sh
# Generate both Threads and Twitter posts from an article

ARTICLE_FILE=$1
STREAM=$2

echo "🧵 Generating Threads post..."
cat "$ARTICLE_FILE" | python generate_threads_post.py --stream "$STREAM"

echo ""
echo "🐦 Generating Twitter post..."
cat "$ARTICLE_FILE" | python generate_twitter_post.py --stream "$STREAM"

echo ""
echo "✅ Done! Check the generated files and copy text into your design tool."
```

Usage:
```bash
chmod +x generate_social.sh
./generate_social.sh article.txt advertising
```

---

## 🆘 Support

- Check the `--help` flag on each script for usage examples
- Review error messages (they're usually specific)
- Verify ANTHROPIC_API_KEY is set in `.env`
- For design tool integration, check their respective API docs

---

## 📝 Examples

See the `/examples` directory (if created) for sample inputs and outputs.

Or run with test text:

```bash
echo "AI is transforming advertising. But is it working? New data shows 67% of marketers can't prove ROI on AI tools, despite spending $50B in 2024. The hype is crashing." | python generate_threads_post.py --stream advertising
```
