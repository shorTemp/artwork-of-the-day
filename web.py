"""Local web preview — fetch a random family-friendly artwork and display it."""

import random, json, time as _time
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.request import urlopen, Request
from urllib.parse import urlparse, parse_qs
import json as _json
import history

AIC_API = "https://api.artic.edu/api/v1/artworks"
AIC_HEADERS = {"User-Agent": "ArtworkOfTheDayBot (discord-bot)", "AIC-User-Agent": "ArtworkOfTheDayBot (discord-bot)", "Content-Type": "application/json"}
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


def is_family_friendly(p):
    title = (p.get("title") or "").lower()
    cats = {c.lower() for c in (p.get("category_titles") or [])}
    return p.get("image_id") and not any(t in title for t in BLOCKED_TITLE_TERMS) and not (cats & BLOCKED_CATEGORIES)


def fetch_painting(subject=None):
    query = {"bool": {"must": [
        {"terms": {"artwork_type_title.keyword": ALLOWED_TYPES}},
        {"term": {"is_public_domain": True}},
        {"exists": {"field": "image_id"}},
    ]}}
    if subject:
        query["bool"]["must"].append({"multi_match": {"query": subject, "fields": ["title", "subject_titles"]}})

    url = f"{AIC_API}/search?fields={FIELDS}"
    seen = history.load()
    # Get total count once
    body = _json.dumps({"query": query, "size": 0}).encode()
    req = Request(url, data=body, headers=AIC_HEADERS)
    result = json.loads(urlopen(req).read())
    total = result["pagination"]["total"]
    iiif_url = result.get("config", {}).get("iiif_url", "https://www.artic.edu/iiif/2")
    if total == 0:
        print(f"  No results for subject={subject}")
        return None, iiif_url
    print(f"  Pool: {total} artworks, history: {len(seen)}, subject: {subject}")
    for attempt in range(5):
        fetch_body = {"query": query, "size": 20, "from": 0,
                      "sort": {"_script": {"type": "number", "script": {"source": "Math.random()"}, "order": "asc"}}}
        if subject:
            del fetch_body["sort"]  # keep relevance sorting for subject searches
            fetch_body["from"] = random.randint(0, min(total - 1, 900))
        body = _json.dumps(fetch_body).encode()
        req = Request(url, data=body, headers=AIC_HEADERS)
        try:
            data = json.loads(urlopen(req).read())
        except Exception as e:
            print(f"  Attempt {attempt}: API error: {e}")
            _time.sleep(1)
            continue
        candidates = data.get("data", [])
        for p in candidates:
            if is_family_friendly(p) and p["id"] not in seen:
                print(f"  Found: {p['title']} (attempt {attempt})")
                return p, iiif_url
        print(f"  Attempt {attempt}: {len(candidates)} candidates, none passed filters")
    print(f"  Gave up after 5 attempts")
    return None, iiif_url
    return None, iiif_url


HTML = """<!DOCTYPE html>
<html><head><meta charset="utf-8"><title>Artwork of the Day</title>
<style>
  * {{ box-sizing: border-box; }}
  body {{ font-family: 'gg sans', 'Noto Sans', 'Helvetica Neue', Helvetica, Arial, sans-serif; max-width: 1000px; margin: 2rem auto; padding: 0 1rem; background: #313338; color: #dbdee1; }}
  h1 {{ color: #e4002b; font-family: system-ui, sans-serif; }}
  .actions {{ margin: 1rem 0; display: flex; gap: 0.5rem; flex-wrap: wrap; }}
  button {{ padding: 0.5rem 1rem; border: none; border-radius: 4px; cursor: pointer; font-size: 0.9rem; }}
  .copy {{ background: #e4002b; color: white; }}
  .refresh {{ background: #4e5058; color: white; }}
  .toast {{ position: fixed; top: 1rem; right: 1rem; background: #248046; color: white; padding: 0.75rem 1.5rem; border-radius: 4px; display: none; font-size: 0.9rem; }}

  /* Discord message container */
  .discord-msg {{ display: flex; gap: 1rem; padding: 0.5rem 1rem; margin: 1.5rem 0; }}
  .avatar {{ width: 40px; height: 40px; border-radius: 50%; background: #5865f2; display: flex; align-items: center; justify-content: center; font-size: 1.2rem; flex-shrink: 0; }}
  .msg-body {{ flex: 1; min-width: 0; }}
  .msg-header {{ display: flex; align-items: baseline; gap: 0.5rem; margin-bottom: 0.25rem; }}
  .bot-name {{ color: #f0f0f0; font-weight: 600; font-size: 1rem; }}
  .bot-tag {{ background: #5865f2; color: white; font-size: 0.625rem; font-weight: 600; padding: 1px 4px; border-radius: 3px; text-transform: uppercase; vertical-align: middle; }}
  .msg-time {{ color: #949ba4; font-size: 0.75rem; }}

  /* Discord embed */
  .embed {{ background: #2b2d31; border-left: 4px solid #e4002b; border-radius: 4px; max-width: 520px; padding: 0.5rem 1rem 1rem; margin-top: 0.25rem; }}
  .embed-title {{ color: #00a8fc; font-weight: 600; font-size: 1rem; margin-bottom: 0.5rem; text-decoration: none; }}
  .embed-title:hover {{ text-decoration: underline; }}
  .embed-fields {{ display: grid; grid-template-columns: repeat(3, 1fr); gap: 0.5rem; margin: 0.5rem 0; }}
  .embed-field {{ min-width: 0; }}
  .embed-field.full {{ grid-column: 1 / -1; }}
  .field-name {{ color: #dbdee1; font-weight: 600; font-size: 0.75rem; margin-bottom: 2px; }}
  .field-value {{ color: #b5bac1; font-size: 0.875rem; word-wrap: break-word; }}
  .embed-img {{ max-width: 100%; border-radius: 4px; margin-top: 0.75rem; cursor: pointer; }}
  .embed-footer {{ color: #949ba4; font-size: 0.75rem; margin-top: 0.5rem; line-height: 1.4; }}

  .section-label {{ color: #949ba4; font-size: 0.75rem; text-transform: uppercase; font-weight: 700; letter-spacing: 0.05em; margin: 2rem 0 0.5rem; }}
</style></head>
<body>
  <h1>{heading}</h1>
  {content}
  <div class="toast" id="toast">Copied!</div>
<script>
function copyImg() {{
  const img = document.getElementById('embed-img');
  fetch(img.src).then(r => r.blob()).then(blob => {{
    navigator.clipboard.write([new ClipboardItem({{'image/png': blob.type.startsWith('image/') ? blob : new Blob([blob], {{type:'image/png'}})}})]);
    showToast('Image copied!');
  }}).catch(() => showToast('Copy failed — right-click and copy instead'));
}}
function copyText() {{
  const el = document.getElementById('copy-text');
  navigator.clipboard.writeText(el.innerText).then(() => showToast('Text copied!'));
}}
function showToast(msg) {{
  const t = document.getElementById('toast');
  t.textContent = msg; t.style.display = 'block';
  setTimeout(() => t.style.display = 'none', 2000);
}}
</script>
</body></html>"""


def render(p, iiif_url, subject=None):
    sub_qs = f"?subject={subject}" if subject else ""
    heading = "🎨 Artwork of the Day" + (f" — <em>{subject}</em>" if subject else "")
    if not p:
        msg = f"about \"{subject}\" " if subject else ""
        return HTML.format(content=f"""<p>Couldn't find an artwork {msg}this time.</p>
        <div class="actions"><button class="refresh" onclick="location.href='/{sub_qs}'">🔄 Try Again</button></div>
        <p style="color:#888;font-size:0.85rem">This can happen if the API is slow or all candidates were filtered. Just hit Try Again.</p>""", heading=heading)

    title = p.get('title', 'Unknown')
    artist = p.get('artist_display', 'Unknown')
    date = p.get('date_display', 'Unknown')
    medium = p.get('medium_display', 'Unknown')
    dimensions = p.get('dimensions', 'Unknown')
    origin = p.get('place_of_origin')
    img_url = f"{iiif_url}/{p['image_id']}/full/843,/0/default.jpg"
    link = f"https://www.artic.edu/artworks/{p['id']}"
    alt = (p.get("thumbnail") or {}).get("alt_text", title)
    footer = alt if alt != title else ""

    origin_field = f"""<div class="embed-field"><div class="field-name">Origin</div><div class="field-value">{origin}</div></div>""" if origin else ""

    content = f"""
    <div class="section-label">Discord Preview</div>
    <div class="discord-msg">
      <div class="avatar">🎨</div>
      <div class="msg-body">
        <div class="msg-header">
          <span class="bot-name">Artwork of the Day</span>
          <span class="bot-tag">Bot</span>
          <span class="msg-time">Today at 7:00 AM</span>
        </div>
        <div class="embed">
          <a class="embed-title" href="{link}" target="_blank">🎨 Artwork of the Day: {title}</a>
          <div class="embed-fields">
            <div class="embed-field"><div class="field-name">Artist</div><div class="field-value">{artist}</div></div>
            <div class="embed-field"><div class="field-name">Date</div><div class="field-value">{date}</div></div>
            {origin_field}
            <div class="embed-field full"><div class="field-name">Medium</div><div class="field-value">{medium}</div></div>
            <div class="embed-field full"><div class="field-name">Dimensions</div><div class="field-value">{dimensions}</div></div>
          </div>
          <img class="embed-img" id="embed-img" src="{img_url}" alt="{alt}" onclick="copyImg()">
          {'<div class="embed-footer">' + footer + '</div>' if footer else ''}
        </div>
      </div>
    </div>

    <div id="copy-text" style="display:none">{title}
Artist: {artist}
Date: {date}
Medium: {medium}
Dimensions: {dimensions}
{link}</div>

    <div class="actions">
      <button class="copy" onclick="copyImg()">📋 Copy Image</button>
      <button class="copy" onclick="copyText()">📝 Copy Text</button>
      <button class="refresh" onclick="location.href='/{sub_qs}'">🔄 New Painting</button>
    </div>"""
    return HTML.format(content=content, heading=heading)


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == "/favicon.ico":
            self.send_response(204)
            self.end_headers()
            return
        qs = parse_qs(urlparse(self.path).query)
        subject = qs.get("subject", [None])[0]
        self.send_response(200)
        self.send_header("Content-Type", "text/html")
        self.end_headers()
        try:
            p, iiif_url = fetch_painting(subject)
        except Exception as e:
            print(f"  ERROR: {e}")
            p, iiif_url = None, ""
        self.wfile.write(render(p, iiif_url, subject).encode())
    def log_message(self, fmt, *args):
        print(f"  {args[0]}")


if __name__ == "__main__":
    port = 8888
    print(f"Open http://localhost:{port} — refresh for a new painting")
    HTTPServer(("", port), Handler).serve_forever()
