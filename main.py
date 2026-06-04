from fastapi import FastAPI, Request, Form
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse, PlainTextResponse
import httpx
import os
import re
import json

INSTAGRAM_TOKEN = os.environ.get("INSTAGRAM_TOKEN", "IGAASawBMiF8hBZAFlQdmxEUDVTZA3loN256TU51Tmo4eVQ5UUVXZAXJjNExTTnlUWjZA4ZA2tZAc3lfbXRGMTFMR3BaV1BuZAGFYQmNnMHllQkpBNGROMWFaWHlkVFFnQkQxeGd0ZAGxGVWVZAanJSeEl1S1hMRzZAlZAnRZAQ3NpT252Q01wOAZDZD")
WHATSAPP = os.environ.get("WHATSAPP", "917411946743")
VERIFY_TOKEN = os.environ.get("VERIFY_TOKEN", "carbot_verify_2024")
DATABASE_URL = os.environ.get("DATABASE_URL", "")
DATA_FILE = "/tmp/cars.json"
REPLIED_FILE = "/tmp/replied.json"

app = FastAPI()


def load_cars():
    # Try PostgreSQL first
    if DATABASE_URL:
        try:
            import psycopg2
            conn = psycopg2.connect(DATABASE_URL)
            cur = conn.cursor()
            cur.execute("SELECT id, reel_id, reel_url, car_name, price, year, km, condition, reply_text, active FROM cars ORDER BY id DESC")
            rows = cur.fetchall()
            cur.close()
            conn.close()
            keys = ["id", "reel_id", "reel_url", "car_name", "price", "year", "km", "condition", "reply_text", "active"]
            return [dict(zip(keys, r)) for r in rows]
        except Exception as e:
            print(f"DB error: {e}")
    # Fallback to file
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE) as f:
            return json.load(f)
    return []


def save_cars(cars):
    if DATABASE_URL:
        try:
            import psycopg2
            conn = psycopg2.connect(DATABASE_URL)
            cur = conn.cursor()
            cur.execute("CREATE TABLE IF NOT EXISTS cars (id SERIAL PRIMARY KEY, reel_id TEXT, reel_url TEXT, car_name TEXT, price TEXT, year TEXT, km TEXT, condition TEXT, reply_text TEXT, active INTEGER DEFAULT 1)")
            conn.commit()
            cur.close()
            conn.close()
        except Exception as e:
            print(f"DB save error: {e}")
    with open(DATA_FILE, "w") as f:
        json.dump(cars, f)


def load_replied():
    if os.path.exists(REPLIED_FILE):
        with open(REPLIED_FILE) as f:
            return set(json.load(f))
    return set()


def save_replied(replied):
    with open(REPLIED_FILE, "w") as f:
        json.dump(list(replied), f)


def get_next_id(cars):
    return max((c["id"] for c in cars), default=0) + 1


def extract_reel_shortcode(url: str) -> str:
    match = re.search(r"/reel/([A-Za-z0-9_-]+)", url)
    return match.group(1) if match else ""


async def get_media_id_from_shortcode(shortcode: str) -> str:
    async with httpx.AsyncClient() as client:
        r = await client.get(
            "https://graph.instagram.com/me/media",
            params={"fields": "id,permalink", "access_token": INSTAGRAM_TOKEN, "limit": 50},
        )
        for item in r.json().get("data", []):
            if shortcode in item.get("permalink", ""):
                return item["id"]
    return shortcode


async def post_reply(comment_id: str, message: str):
    async with httpx.AsyncClient() as client:
        r = await client.post(
            f"https://graph.instagram.com/{comment_id}/replies",
            params={"access_token": INSTAGRAM_TOKEN},
            json={"message": message},
        )
        return r.json()


DASHBOARD_HTML = """<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>CarBot Dashboard</title>
<style>
  * { box-sizing: border-box; margin: 0; padding: 0; }
  body { font-family: -apple-system, sans-serif; background: #f0f2f5; }
  .header { background: #1877f2; color: white; padding: 16px 24px; display: flex; align-items: center; gap: 12px; }
  .header h1 { font-size: 20px; font-weight: 700; }
  .container { max-width: 900px; margin: 24px auto; padding: 0 16px; }
  .card { background: white; border-radius: 12px; padding: 24px; margin-bottom: 20px; box-shadow: 0 1px 4px rgba(0,0,0,0.1); }
  .card h2 { font-size: 16px; font-weight: 700; margin-bottom: 16px; color: #1877f2; }
  .form-row { display: grid; grid-template-columns: 1fr 1fr; gap: 12px; margin-bottom: 12px; }
  .form-row.full { grid-template-columns: 1fr; }
  label { display: block; font-size: 13px; font-weight: 600; margin-bottom: 4px; color: #444; }
  input, textarea { width: 100%; padding: 10px 12px; border: 1px solid #ddd; border-radius: 8px; font-size: 14px; outline: none; }
  input:focus, textarea:focus { border-color: #1877f2; }
  textarea { resize: vertical; min-height: 90px; }
  .btn { background: #1877f2; color: white; border: none; padding: 12px 24px; border-radius: 8px; font-size: 14px; font-weight: 600; cursor: pointer; width: 100%; margin-top: 8px; }
  .btn-danger { background: #e53935; font-size: 12px; padding: 6px 12px; width: auto; margin: 0; border: none; border-radius: 6px; color: white; cursor: pointer; }
  .btn-toggle { background: #43a047; font-size: 12px; padding: 6px 12px; width: auto; margin: 0; border: none; border-radius: 6px; color: white; cursor: pointer; }
  .car-list { display: flex; flex-direction: column; gap: 12px; }
  .car-item { border: 1px solid #eee; border-radius: 10px; padding: 16px; display: flex; justify-content: space-between; align-items: flex-start; gap: 12px; }
  .car-item.inactive { opacity: 0.5; }
  .car-info h3 { font-size: 15px; font-weight: 700; }
  .car-info p { font-size: 13px; color: #666; margin-top: 4px; }
  .reply-preview { font-size: 12px; color: #888; margin-top: 6px; background: #f5f5f5; padding: 8px; border-radius: 6px; }
  .car-actions { display: flex; gap: 8px; flex-shrink: 0; }
  .badge { display: inline-block; padding: 2px 8px; border-radius: 20px; font-size: 11px; font-weight: 700; margin-top: 4px; }
  .badge-on { background: #e8f5e9; color: #2e7d32; }
  .badge-off { background: #fce4ec; color: #b71c1c; }
  .hint { font-size: 12px; color: #888; margin-top: 4px; }
  .empty { text-align: center; color: #aaa; padding: 32px; }
</style>
</head>
<body>
<div class="header"><span style="font-size:24px">🚗</span><h1>CarBot — Auto Reply Dashboard</h1></div>
<div class="container">
  <div class="card">
    <h2>➕ Add New Car + Link Reel</h2>
    <form method="POST" action="/cars">
      <div class="form-row">
        <div><label>Car Name *</label><input name="car_name" placeholder="e.g. Maruti Swift VXI 2019" required></div>
        <div><label>Price *</label><input name="price" placeholder="e.g. ₹4.5 Lakh" required></div>
      </div>
      <div class="form-row">
        <div><label>Year</label><input name="year" placeholder="e.g. 2019"></div>
        <div><label>KMs Driven</label><input name="km" placeholder="e.g. 45,000 KM"></div>
      </div>
      <div class="form-row">
        <div><label>Condition</label><input name="condition" placeholder="e.g. Excellent, Single Owner"></div>
        <div><label>Reel URL *</label><input name="reel_url" placeholder="https://www.instagram.com/reel/..." required><p class="hint">Paste full Instagram reel link</p></div>
      </div>
      <div class="form-row full">
        <div><label>Auto Reply Message *</label>
        <textarea name="reply_text" required placeholder="Hi! Thanks for your interest&#10;Car: Maruti Swift VXI 2019&#10;Price: ₹4.5 Lakh&#10;Contact: wa.me/917411946743"></textarea>
        <p class="hint">This exact message will be posted as reply to every comment on this reel</p></div>
      </div>
      <button type="submit" class="btn">✅ Save Car & Activate Auto Reply</button>
    </form>
  </div>
  <div class="card">
    <h2>🎬 Your Active Cars</h2>
    {% if cars %}
    <div class="car-list">
      {% for car in cars %}
      <div class="car-item {% if not car.active %}inactive{% endif %}">
        <div class="car-info">
          <h3>{{ car.car_name }}</h3>
          <p>💰 {{ car.price }} | 📅 {{ car.year or '—' }} | 🛣️ {{ car.km or '—' }}</p>
          <p>🔗 <a href="{{ car.reel_url }}" target="_blank" style="color:#1877f2">View Reel</a> | ID: <code>{{ car.reel_id }}</code></p>
          <span class="badge {% if car.active %}badge-on{% else %}badge-off{% endif %}">{% if car.active %}🟢 Replying{% else %}🔴 Paused{% endif %}</span>
          <div class="reply-preview">{{ car.reply_text[:150] }}...</div>
        </div>
        <div class="car-actions">
          <form method="POST" action="/cars/{{ car.id }}/toggle"><button class="btn-toggle" type="submit">{% if car.active %}Pause{% else %}Resume{% endif %}</button></form>
          <form method="POST" action="/cars/{{ car.id }}/delete"><button class="btn-danger" type="submit">Delete</button></form>
        </div>
      </div>
      {% endfor %}
    </div>
    {% else %}<div class="empty">No cars added yet. Add your first car above!</div>{% endif %}
  </div>
</div>
</body></html>"""


@app.get("/", response_class=HTMLResponse)
async def dashboard():
    cars = load_cars()
    from jinja2 import Template
    return Template(DASHBOARD_HTML).render(cars=cars)


@app.post("/cars")
async def add_car(
    car_name: str = Form(...), price: str = Form(...), year: str = Form(""),
    km: str = Form(""), condition: str = Form(""), reel_url: str = Form(...), reply_text: str = Form(...),
):
    shortcode = extract_reel_shortcode(reel_url)
    media_id = await get_media_id_from_shortcode(shortcode) if shortcode else reel_url
    cars = load_cars()
    cars.insert(0, {
        "id": get_next_id(cars), "reel_id": media_id, "reel_url": reel_url,
        "car_name": car_name, "price": price, "year": year, "km": km,
        "condition": condition, "reply_text": reply_text, "active": 1
    })
    save_cars(cars)
    return RedirectResponse("/", status_code=303)


@app.post("/cars/{car_id}/toggle")
async def toggle_car(car_id: int):
    cars = load_cars()
    for c in cars:
        if c["id"] == car_id:
            c["active"] = 1 - c["active"]
    save_cars(cars)
    return RedirectResponse("/", status_code=303)


@app.post("/cars/{car_id}/delete")
async def delete_car(car_id: int):
    cars = [c for c in load_cars() if c["id"] != car_id]
    save_cars(cars)
    return RedirectResponse("/", status_code=303)


@app.get("/webhook")
async def verify_webhook(request: Request):
    params = dict(request.query_params)
    if params.get("hub.mode") == "subscribe" and params.get("hub.verify_token") == VERIFY_TOKEN:
        return PlainTextResponse(content=params["hub.challenge"])
    return JSONResponse({"error": "Invalid verify token"}, status_code=403)


@app.post("/webhook")
async def handle_webhook(request: Request):
    body = await request.json()
    print("WEBHOOK:", body)
    cars = load_cars()
    replied = load_replied()

    for entry in body.get("entry", []):
        for change in entry.get("changes", []):
            if change.get("field") != "comments":
                continue
            value = change.get("value", {})
            comment_id = value.get("id")
            media_id = value.get("media", {}).get("id", "")
            print(f"comment={comment_id} media={media_id}")

            if not comment_id or comment_id in replied:
                continue

            car = next((c for c in cars if c["reel_id"] == media_id and c["active"]), None)
            print(f"car={car}")
            if car:
                result = await post_reply(comment_id, car["reply_text"])
                print(f"reply result={result}")
                replied.add(comment_id)
                save_replied(replied)

    return JSONResponse({"status": "ok"})


@app.get("/health")
async def health():
    return {"status": "running", "whatsapp": WHATSAPP}


@app.get("/debug")
async def debug():
    return {"cars": load_cars(), "replied_count": len(load_replied())}


@app.get("/privacy", response_class=HTMLResponse)
async def privacy():
    return "<html><body><h1>Privacy Policy</h1><p>CarBot replies to Instagram comments for BudgetBro Automotive. No personal data stored or shared.</p></body></html>"
