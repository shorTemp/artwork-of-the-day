import os
import random
import discord
from discord.ext import commands, tasks
from datetime import time
import aiohttp
import asyncio
import io
import history

BOT_TOKEN = os.environ["DISCORD_BOT_TOKEN"]
CHANNEL_ID = int(os.environ["DISCORD_CHANNEL_ID"])

# Post daily at 7:00 AM CST (13:00 UTC)
POST_TIME = time(hour=13, minute=0)

AIC_API = "https://api.artic.edu/api/v1/artworks"
AIC_HEADERS = {"AIC-User-Agent": "ArtworkOfTheDayBot (discord-bot)"}
FIELDS = "id,title,artist_display,date_display,medium_display,dimensions,place_of_origin,image_id,thumbnail,category_titles,is_public_domain"
ALLOWED_TYPES = ["Painting", "Drawing and Watercolor", "Miniature Painting"]

BLOCKED_CATEGORIES = {
    "nudes", "nudity", "erotic images", "sexuality",
    "breasts", "genitalia", "prostitutes",
    "bath", "bathing", "baths", "sun bathe",
    "venus", "satyr", "fauns/satyrs/pan", "fertility",
    "underwear",
}
BLOCKED_TITLE_TERMS = {
    "nude", "naked", "erotic", "bather", "bathers",
    "odalisque", "harem", "courtesan",
}

intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)


def is_family_friendly(p):
    title = (p.get("title") or "").lower()
    cats = {c.lower() for c in (p.get("category_titles") or [])}
    return (
        p.get("image_id")
        and not any(t in title for t in BLOCKED_TITLE_TERMS)
        and not (cats & BLOCKED_CATEGORIES)
    )


async def fetch_painting(subject=None, max_attempts=5):
    query = {"bool": {"must": [
        {"terms": {"artwork_type_title.keyword": ALLOWED_TYPES}},
        {"term": {"is_public_domain": True}},
        {"exists": {"field": "image_id"}},
    ]}}
    if subject:
        query["bool"]["must"].append({"multi_match": {"query": subject, "fields": ["title", "subject_titles"]}})

    url = f"{AIC_API}/search?fields={FIELDS}"
    seen = history.load()
    async with aiohttp.ClientSession(headers=AIC_HEADERS) as session:
        async with session.post(url, json={"query": query, "size": 0}) as resp:
            result = await resp.json()
            total = result["pagination"]["total"]
            iiif_url = result.get("config", {}).get("iiif_url", "https://www.artic.edu/iiif/2")
        if total == 0:
            return None, iiif_url
        for _ in range(max_attempts):
            fetch_body = {"query": query, "size": 20, "from": 0,
                          "sort": {"_script": {"type": "number", "script": {"source": "Math.random()"}, "order": "asc"}}}
            if subject:
                del fetch_body["sort"]
                fetch_body["from"] = random.randint(0, min(total - 1, 900))
            try:
                async with session.post(url, json=fetch_body) as resp:
                    data = await resp.json()
            except Exception:
                await asyncio.sleep(1)
                continue
            for p in data.get("data", []):
                if is_family_friendly(p) and p["id"] not in seen:
                    history.check_and_add(p["id"])
                    return p, iiif_url
    return None, iiif_url


def build_embed(painting, iiif_url):
    title = painting.get("title", "Unknown Title")
    artist = painting.get("artist_display", "Unknown Artist")
    date = painting.get("date_display", "Unknown Date")
    medium = painting.get("medium_display", "Unknown Medium")
    dimensions = painting.get("dimensions", "Unknown Dimensions")
    origin = painting.get("place_of_origin")

    embed = discord.Embed(
        title=f"🎨 Artwork of the Day: {title}",
        url=f"https://www.artic.edu/artworks/{painting['id']}",
        color=0xE4002B,
    )
    embed.add_field(name="Artist", value=artist, inline=True)
    embed.add_field(name="Date", value=date, inline=True)
    if origin:
        embed.add_field(name="Origin", value=origin, inline=True)
    embed.add_field(name="Medium", value=medium, inline=False)
    embed.add_field(name="Dimensions", value=dimensions, inline=False)

    image_id = painting.get("image_id")
    if image_id:
        embed.set_image(url=f"attachment://artwork.jpg")

    alt = painting.get("thumbnail") or {}
    if alt.get("alt_text"):
        embed.set_footer(text=alt["alt_text"])

    return embed


async def download_image(painting, iiif_url):
    image_id = painting.get("image_id")
    if not image_id:
        return None
    url = f"{iiif_url}/{image_id}/full/843,/0/default.jpg"
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as resp:
            if resp.status == 200:
                data = await resp.read()
                return discord.File(io.BytesIO(data), filename="artwork.jpg")
    return None


@bot.event
async def on_ready():
    print(f"Logged in as {bot.user}", flush=True)
    if not daily_painting.is_running():
        daily_painting.start()


@tasks.loop(time=POST_TIME)
async def daily_painting():
    channel = bot.get_channel(CHANNEL_ID)
    if not channel:
        return
    painting, iiif_url = await fetch_painting()
    if not painting:
        await channel.send("Couldn't fetch an artwork today — try again tomorrow! 🖼️")
        return
    file = await download_image(painting, iiif_url)
    await channel.send(embed=build_embed(painting, iiif_url), file=file)


@bot.command()
async def artwork(ctx, *, subject: str = None):
    """Manually fetch a random artwork. Optionally provide a subject like !artwork trains"""
    p, iiif_url = await fetch_painting(subject=subject)
    if not p:
        msg = f"Couldn't find an artwork about '{subject}'." if subject else "Couldn't fetch an artwork right now."
        await ctx.send(f"{msg} Try again!")
        return
    file = await download_image(p, iiif_url)
    await ctx.send(embed=build_embed(p, iiif_url), file=file)


print("Starting bot...", flush=True)
bot.run(BOT_TOKEN)
