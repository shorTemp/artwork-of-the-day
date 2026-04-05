# Artwork of the Day Discord Bot

Posts a random artwork from the [Art Institute of Chicago](https://www.artic.edu/) to a Discord channel every day at 7:00 AM CST.

## Local Setup

1. **Create a Discord bot** at https://discord.com/developers/applications
   - Enable the `MESSAGE_CONTENT` intent (Settings → Bot → Privileged Gateway Intents)
   - Under OAuth2 → URL Generator, select `bot` scope with `Send Messages` and `Embed Links` permissions
   - Use the generated URL to invite the bot to your server

2. **Get your channel ID**: Enable Developer Mode in Discord (Settings → Advanced), then right-click the target channel → Copy Channel ID

3. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

4. **Set environment variables**:
   ```bash
   export DISCORD_BOT_TOKEN="your-bot-token"
   export DISCORD_CHANNEL_ID="your-channel-id"
   ```

5. **Run**:
   ```bash
   python bot.py
   ```

## Deploy to Railway

1. Push this repo to GitHub
2. Go to https://railway.app → New Project → Deploy from GitHub repo
3. Add environment variables in the Railway dashboard:
   - `DISCORD_BOT_TOKEN` — your bot token
   - `DISCORD_CHANNEL_ID` — your channel ID
   - `HISTORY_DB` — `/data/history.db`
4. Add a volume in Railway:
   - Mount path: `/data`
5. Deploy — Railway will build from the Dockerfile automatically

## Local Web Preview

```bash
python web.py
```
Open http://localhost:8888 to preview artworks with a Discord-style embed mockup.
- `?subject=trains` — filter by subject
- Copy Image / Copy Text buttons for manual posting

## Commands

- `!artwork` — Manually fetch and post a random artwork
- `!artwork trains` — Fetch an artwork about a specific subject

## What gets posted

Each post includes:
- Artwork title (linked to the AIC website)
- Artist name, nationality, and lifespan
- Date of creation
- Place of origin
- Medium (oil on canvas, watercolor, etc.)
- Dimensions
- High-res image
- Alt text description (when available)

All artworks are public domain and family-friendly filtered.
