# Social Media Automation Setup Guide

## Overview

You now have **two scripts** for romantasy social media automation:

1. **`automate_romantasy_social.py`** - Fully automated (generates and saves content)
2. **`automate_romantasy_social_interactive.py`** - Interactive with human-in-the-loop (RECOMMENDED)

## Quick Start (Interactive Mode)

```bash
python automate_romantasy_social_interactive.py
```

The interactive script will guide you through each step and let you review/regenerate content before posting.

---

## Required API Setup

### 1. Core Requirements (Always Needed)

```bash
# In your .env file:
ANTHROPIC_API_KEY=your_key_here          # For content generation
GOOGLE_API_KEY=your_gemini_key           # For image generation
```

### 2. Optional: Image Formatting

```bash
APILAYER_API_KEY=your_key_here           # For optimizing images (optional but recommended)
```

Get your API key at: https://apilayer.com/marketplace/social_media_assets_generator-api

---

## Platform Posting Setup (Optional)

If you want to actually **post** to platforms (not just generate content):

### Twitter API Setup

1. Go to: https://developer.twitter.com/en/portal/dashboard
2. Create a new app (or use existing)
3. Generate keys under "Keys and Tokens"
4. Add to `.env`:

```bash
TWITTER_API_KEY=your_consumer_key
TWITTER_API_SECRET=your_consumer_secret
TWITTER_ACCESS_TOKEN=your_access_token
TWITTER_ACCESS_SECRET=your_access_token_secret
```

5. Install tweepy: `pip install tweepy`

### Threads API Setup

1. Go to: https://developers.facebook.com/
2. Create app and get Threads access
3. Generate access token with `threads_basic` and `threads_content_publish` permissions
4. Add to `.env`:

```bash
META_ACCESS_TOKEN=your_access_token
META_USER_ID=your_threads_user_id
```

### Pinterest API Setup

1. Go to: https://developers.pinterest.com/apps/
2. Create app and get API credentials
3. Generate access token with write permissions
4. Create a board and get its ID
5. Add to `.env`:

```bash
PINTEREST_ACCESS_TOKEN=your_access_token
PINTEREST_BOARD_ID=your_board_id
```

### Instagram Setup

Instagram posting is more complex and requires manual approval. The script will **email** you the post instead:

```bash
EMAIL_FROM=your_email@gmail.com
EMAIL_TO=your_email@gmail.com
SMTP_USER=your_email@gmail.com
SMTP_PASSWORD=your_app_password          # NOT your regular Gmail password
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
```

**Gmail App Password Setup:**
1. Enable 2-factor authentication on your Gmail account
2. Go to: https://myaccount.google.com/apppasswords
3. Generate an app password for "Mail"
4. Use that password (not your regular password)

---

## Usage Examples

### Interactive Mode (Recommended)

```bash
# Run interactively - review each step:
python automate_romantasy_social_interactive.py

# The script will prompt you to:
# 1. Generate/provide topic
# 2. Review and regenerate posts
# 3. Review and regenerate images
# 4. Confirm before posting
```

### Automated Mode

```bash
# Generate content only (no posting):
python automate_romantasy_social.py --dry-run

# Generate and save for manual posting:
python automate_romantasy_social.py

# Use specific topic:
python automate_romantasy_social.py --topic "How to Write Enemies-to-Lovers"

# Skip images:
python automate_romantasy_social.py --no-images
```

---

## What Gets Posted Where

| Platform  | Character Limit | Content Style              | Auto-Post? |
|-----------|----------------|----------------------------|------------|
| Twitter   | 280 chars      | Hook + insight + question  | ✅ Yes      |
| Threads   | 500 chars      | Personal + conversational  | ✅ Yes      |
| Pinterest | 500 chars      | SEO-optimized, educational | ✅ Yes      |
| Instagram | 2200 chars     | Story-driven + tips        | 📧 Email    |

---

## Troubleshooting

### "tweepy not installed"
```bash
pip install tweepy
```

### "google-genai not installed"
```bash
pip install google-genai
```

### Twitter API errors
- Make sure you have **Elevated access** (not just Essential)
- Check that your app has **Read and Write** permissions
- Regenerate tokens if you changed permissions

### Threads/Meta API errors
- Ensure access token has `threads_basic` and `threads_content_publish` scopes
- Check token hasn't expired (Meta tokens expire after 60 days by default)

### Pinterest API errors
- Verify you have write permissions on the board
- Make sure images are publicly accessible if using URLs

### Gmail "Authentication failed"
- Use an **App Password**, not your regular Gmail password
- Enable 2-factor authentication first
- Check SMTP_HOST and SMTP_PORT are correct

---

## Security Best Practices

1. **Never commit API keys to git**
   - Keep them in `.env` file (already in `.gitignore`)

2. **Use environment variables**
   ```bash
   export ANTHROPIC_API_KEY="your_key"
   # or use .env file (recommended)
   ```

3. **Rotate keys periodically**
   - Especially if you share code or screenshots

4. **Limit API permissions**
   - Only grant minimum required scopes
   - Use separate keys for dev/prod if available

---

## Cost Estimates

| Service          | Free Tier           | Cost After Free Tier    |
|------------------|---------------------|-------------------------|
| Anthropic Claude | No free tier        | ~$0.01 per post         |
| Google Gemini    | Free tier available | ~$0.002 per image       |
| apilayer         | 100 calls/month     | $10/month (1000 calls)  |
| Twitter API      | Free (limits apply) | Free or $100/month      |
| Meta Graph API   | Free                | Free                    |
| Pinterest API    | Free                | Free                    |

**Estimated cost per post:** ~$0.01-0.02 (if generating 4 images + text)

---

## Next Steps

1. Set up your API keys in `.env`
2. Test with dry-run mode first: `python automate_romantasy_social.py --dry-run`
3. Try interactive mode: `python automate_romantasy_social_interactive.py`
4. Set up platform APIs only when ready to auto-post

**Questions?** Check the inline help:
```bash
python automate_romantasy_social_interactive.py --help
```
