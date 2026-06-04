from fastapi import FastAPI, Request, Form
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse, PlainTextResponse
import sqlite3
import httpx
import os
import re

INSTAGRAM_TOKEN = os.environ.get("INSTAGRAM_TOKEN", "IGAASawBMiF8hBZAFlQdmxEUDVTZA3loN256TU51Tmo4eVQ5UUVXZAXJjNExTTnlUWjZA4ZA2tZAc3lfbXRGMTFMR3BaV1BuZAGFYQmNnMHllQkpBNGROMWFaWHlkVFFnQkQxeGd0ZAGxGVWVZAanJSeEl1S1hMRzZAlZAnRZAQ3NpT252Q01wOAZDZD")
INSTAGRAM_USER_ID = os.environ.get("INSTAGRAM_USER_ID", "26923771167245963")
WHATSAPP = os.environ.get("WHATSAPP", "917411946743")
VERIFY_TOKEN = os.environ.get("VERIFY_TOKEN", "carbot_verify_2024")

app = FastAPI()


def get_db():
    conn = sqlite3.connect("cars.db")
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_db()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS cars (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            reel_id TEXT NOT NULL,
            reel_url TEXT,
            car_name TEXT NOT NULL,
            price TEXT NOT NULL,
            year TEXT,
            km TEXT,
            condition TEXT,
            reply_text TEXT NOT NULL,
            active INTEGER DEFAULT 1,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS replied_comments (
            comment_id TEXT PRIMARY KEY,
            replied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.commit()
    conn.close()


init_db()


def extract_reel_shortcode(url: str) -> str:
    match = re.search(r"/reel/([A-Za-z0-9_-]+)", url)
    return match.group(1) if match else ""


async def get_media_id_from_shortcode(shortcode: str) -> str:
    """Fetch recent media and match by shortcode in permalink."""
    async with httpx.AsyncClient() as client:
        r = await client.get(
            f"https://graph.instagram.com/me/media",
            params={
                "fields": "id,permalink,media_type",
                "access_token": INSTAGRAM_TOKEN,
                "limit": 50,
            },
        )
        data = r.json()
        for item in data.get("data", []):
            if shortcode in item.get("permalink", ""):
                return item["id"]
    return ""


async def post_reply(comment_id: str, message: str):
    async with httpx.AsyncClient() as client:
        r = await client.post(
            f"https://graph.instagram.com/{comment_id}/replies",
            params={"access_token": INSTAGRAM_TOKEN},
            json={"message": message},
        )
        return r.json()


async def fetch_recent_reels():
    async with httpx.AsyncClient() as client:
        r = await client.get(
            "https://graph.instagram.com/me/media",
            params={
                "fields": "id,caption,media_type,permalink,timestamp",
                "access_token": INSTAGRAM_TOKEN,
                "limit": 20,
            },
        )
        data = r.json()
        return [
            m for m in data.get("data", [])
            if m.get("media_type") in ("VIDEO", "REEL")
        ]


DASHBOARD_HTML = """
<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>CarBot Dashboard</title>
<style>
  * { box-sizing: border-box; margin: 0; padding: 0; }
  body { font-family: -apple-system, sans-serif; background: #f0f2f5; color: #1a1a1a; }
  .header { background: #1877f2; color: white; padding: 16px 24px; display: flex; align-items: center; gap: 12px; }
  .header h1 { font-size: 20px; font-weight: 700; }
  .container { max-width: 900px; margin: 24px auto; padding: 0 16px; }
  .card { background: white; border-radius: 12px; padding: 24px; margin-bottom: 20px; box-shadow: 0 1px 4px rgba(0,0,0,0.1); }
  .card h2 { font-size: 16px; font-weight: 700; margin-bottom: 16px; color: #1877f2; }
  .form-row { display: grid; grid-template-columns: 1fr 1fr; gap: 12px; margin-bottom: 12px; }
  .form-row.full { grid-template-columns: 1fr; }
  label { display: block; font-size: 13px; font-weight: 600; margin-bottom: 4px; color: #444; }
  input, textarea, select { width: 100%; padding: 10px 12px; border: 1px solid #ddd; border-radius: 8px; font-size: 14px; outline: none; }
  input:focus, textarea:focus { border-color: #1877f2; }
  textarea { resize: vertical; min-height: 90px; }
  .btn { background: #1877f2; color: white; border: none; padding: 12px 24px; border-radius: 8px; font-size: 14px; font-weight: 600; cursor: pointer; width: 100%; margin-top: 8px; }
  .btn:hover { background: #166fe5; }
  .btn-danger { background: #e53935; font-size: 12px; padding: 6px 12px; width: auto; margin: 0; }
  .btn-toggle { background: #43a047; font-size: 12px; padding: 6px 12px; width: auto; margin: 0; }
  .car-list { display: flex; flex-direction: column; gap: 12px; }
  .car-item { border: 1px solid #eee; border-radius: 10px; padding: 16px; display: flex; justify-content: space-between; align-items: flex-start; gap: 12px; }
  .car-item.inactive { opacity: 0.5; }
  .car-info h3 { font-size: 15px; font-weight: 700; }
  .car-info p { font-size: 13px; color: #666; margin-top: 4px; }
  .car-info .reply-preview { font-size: 12px; color: #888; margin-top: 6px; background: #f5f5f5; padding: 8px; border-radius: 6px; }
  .car-actions { display: flex; gap: 8px; flex-shrink: 0; }
  .badge { display: inline-block; padding: 2px 8px; border-radius: 20px; font-size: 11px; font-weight: 700; margin-top: 4px; }
  .badge-on { background: #e8f5e9; color: #2e7d32; }
  .badge-off { background: #fce4ec; color: #b71c1c; }
  .hint { font-size: 12px; color: #888; margin-top: 4px; }
  .reels-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(200px, 1fr)); gap: 10px; margin-top: 12px; }
  .reel-card { border: 2px solid #eee; border-radius: 8px; padding: 10px; cursor: pointer; font-size: 12px; }
  .reel-card:hover { border-color: #1877f2; }
  .reel-card p { color: #555; margin-top: 4px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
  .empty { text-align: center; color: #aaa; padding: 32px; }
</style>
</head>
<body>
<div class="header">
  <span style="font-size:24px">🚗</span>
  <h1>CarBot — Auto Reply Dashboard</h1>
</div>
<div class="container">

  <div class="card">
    <h2>➕ Add New Car + Link Reel</h2>
    <form method="POST" action="/cars">
      <div class="form-row">
        <div>
          <label>Car Name *</label>
          <input name="car_name" placeholder="e.g. Maruti Swift VXI 2019" required>
        </div>
        <div>
          <label>Price *</label>
          <input name="price" placeholder="e.g. ₹4.5 Lakh" required>
        </div>
      </div>
      <div class="form-row">
        <div>
          <label>Year</label>
          <input name="year" placeholder="e.g. 2019">
        </div>
        <div>
          <label>KMs Driven</label>
          <input name="km" placeholder="e.g. 45,000 KM">
        </div>
      </div>
      <div class="form-row">
        <div>
          <label>Condition</label>
          <input name="condition" placeholder="e.g. Excellent, Single Owner">
        </div>
        <div>
          <label>Reel URL *</label>
          <input name="reel_url" placeholder="https://www.instagram.com/reel/..." required>
          <p class="hint">Paste the full Instagram reel link</p>
        </div>
      </div>
      <div class="form-row full">
        <div>
          <label>Auto Reply Message *</label>
          <textarea name="reply_text" required placeholder="Hi! Thanks for your interest 🚗&#10;&#10;Car: Maruti Swift VXI 2019&#10;Price: ₹4.5 Lakh&#10;KMs: 45,000 KM | Single Owner&#10;&#10;Contact us on WhatsApp for test drive & more details 👇&#10;wa.me/917411946743"></textarea>
          <p class="hint">This exact message will be posted as reply to every comment on this reel</p>
        </div>
      </div>
      <button type="submit" class="btn">✅ Save Car & Activate Auto Reply</button>
    </form>
  </div>

  <div class="card">
    <h2>🎬 Your Active Cars</h2>
    {% if cars %}
    <div class="car-list">
      {% for car in cars %}
      <div class="car-item {% if not car['active'] %}inactive{% endif %}">
        <div class="car-info">
          <h3>{{ car['car_name'] }}</h3>
          <p>💰 {{ car['price'] }} &nbsp;|&nbsp; 📅 {{ car['year'] or '—' }} &nbsp;|&nbsp; 🛣️ {{ car['km'] or '—' }}</p>
          <p>🔗 <a href="{{ car['reel_url'] }}" target="_blank" style="color:#1877f2">View Reel</a></p>
          <span class="badge {% if car['active'] %}badge-on{% else %}badge-off{% endif %}">
            {% if car['active'] %}🟢 Replying{% else %}🔴 Paused{% endif %}
          </span>
          <div class="reply-preview">{{ car['reply_text'][:120] }}...</div>
        </div>
        <div class="car-actions">
          <form method="POST" action="/cars/{{ car['id'] }}/toggle">
            <button class="btn btn-toggle" type="submit">
              {% if car['active'] %}Pause{% else %}Resume{% endif %}
            </button>
          </form>
          <form method="POST" action="/cars/{{ car['id'] }}/delete">
            <button class="btn btn-danger" type="submit">Delete</button>
          </form>
        </div>
      </div>
      {% endfor %}
    </div>
    {% else %}
    <div class="empty">No cars added yet. Add your first car above!</div>
    {% endif %}
  </div>

</div>
</body>
</html>
"""


@app.get("/", response_class=HTMLResponse)
async def dashboard():
    conn = get_db()
    cars = conn.execute("SELECT * FROM cars ORDER BY created_at DESC").fetchall()
    conn.close()
    html = DASHBOARD_HTML.replace("{% if cars %}", "" if cars else "<!--").replace(
        "{% else %}", "" if not cars else "<!--"
    )
    # Simple template rendering
    from jinja2 import Template
    tmpl = Template(DASHBOARD_HTML)
    return tmpl.render(cars=[dict(c) for c in cars])


@app.post("/cars")
async def add_car(
    car_name: str = Form(...),
    price: str = Form(...),
    year: str = Form(""),
    km: str = Form(""),
    condition: str = Form(""),
    reel_url: str = Form(...),
    reply_text: str = Form(...),
):
    shortcode = extract_reel_shortcode(reel_url)
    media_id = await get_media_id_from_shortcode(shortcode) if shortcode else ""

    conn = get_db()
    conn.execute(
        "INSERT INTO cars (reel_id, reel_url, car_name, price, year, km, condition, reply_text) VALUES (?,?,?,?,?,?,?,?)",
        (media_id or shortcode, reel_url, car_name, price, year, km, condition, reply_text),
    )
    conn.commit()
    conn.close()
    return RedirectResponse("/", status_code=303)


@app.post("/cars/{car_id}/toggle")
async def toggle_car(car_id: int):
    conn = get_db()
    conn.execute("UPDATE cars SET active = 1 - active WHERE id = ?", (car_id,))
    conn.commit()
    conn.close()
    return RedirectResponse("/", status_code=303)


@app.post("/cars/{car_id}/delete")
async def delete_car(car_id: int):
    conn = get_db()
    conn.execute("DELETE FROM cars WHERE id = ?", (car_id,))
    conn.commit()
    conn.close()
    return RedirectResponse("/", status_code=303)


@app.get("/webhook")
async def verify_webhook(request: Request):
    params = dict(request.query_params)
    if (
        params.get("hub.mode") == "subscribe"
        and params.get("hub.verify_token") == VERIFY_TOKEN
    ):
        return PlainTextResponse(content=params["hub.challenge"])
    return JSONResponse({"error": "Invalid verify token"}, status_code=403)


@app.get("/health")
async def health():
    return {"status": "running", "whatsapp": WHATSAPP}


@app.get("/debug")
async def debug():
    conn = get_db()
    cars = conn.execute("SELECT id, reel_id, reel_url, car_name, active FROM cars").fetchall()
    replied = conn.execute("SELECT * FROM replied_comments ORDER BY replied_at DESC LIMIT 10").fetchall()
    conn.close()
    return {
        "cars": [dict(c) for c in cars],
        "recent_replies": [dict(r) for r in replied],
        "token_preview": INSTAGRAM_TOKEN[:20] + "...",
    }


@app.post("/webhook")
async def handle_webhook_debug(request: Request):
    body = await request.json()
    print("WEBHOOK RECEIVED:", body)

    for entry in body.get("entry", []):
        for change in entry.get("changes", []):
            print("CHANGE FIELD:", change.get("field"))
            print("CHANGE VALUE:", change.get("value"))
            if change.get("field") != "comments":
                continue
            value = change.get("value", {})
            comment_id = value.get("id")
            media_id = value.get("media", {}).get("id", "")
            print(f"COMMENT ID: {comment_id}, MEDIA ID: {media_id}")

            if not comment_id or not media_id:
                continue

            conn = get_db()
            already = conn.execute(
                "SELECT 1 FROM replied_comments WHERE comment_id = ?", (comment_id,)
            ).fetchone()
            if already:
                conn.close()
                continue

            car = conn.execute(
                "SELECT * FROM cars WHERE reel_id = ? AND active = 1", (media_id,)
            ).fetchone()
            print(f"CAR FOUND: {dict(car) if car else None}")

            if car:
                result = await post_reply(comment_id, car["reply_text"])
                print(f"REPLY RESULT: {result}")
                conn.execute(
                    "INSERT OR IGNORE INTO replied_comments (comment_id) VALUES (?)",
                    (comment_id,),
                )
                conn.commit()
            conn.close()

    return JSONResponse({"status": "ok"})
