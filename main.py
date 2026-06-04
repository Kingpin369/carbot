from fastapi import FastAPI, Request, Form
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse, PlainTextResponse
import httpx
import os
import re
import json

INSTAGRAM_TOKEN = os.environ.get("INSTAGRAM_TOKEN", "IGAASawBMiF8hBZAFlQdmxEUDVTZA3loN256TU51Tmo4eVQ5UUVXZAXJjNExTTnlUWjZA4ZA2tZAc3lfbXRGMTFMR3BaV1BuZAGFYQmNnMHllQkpBNGROMWFaWHlkVFFnQkQxeGd0ZAGxGVWVZAanJSeEl1S1hMRzZAlZAnRZAQ3NpT252Q01wOAZDZD")
WHATSAPP = os.environ.get("WHATSAPP", "917411946743")
VERIFY_TOKEN = os.environ.get("VERIFY_TOKEN", "carbot_verify_2024")
DATA_FILE = "/tmp/cars.json"
REPLIED_FILE = "/tmp/replied.json"

app = FastAPI()

COMMENT_REPLY = "Thanks for your interest! 😊 We've sent you the full details on DM — please check! 📩"


def load_cars():
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE) as f:
            return json.load(f)
    return []


def save_cars(cars):
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


async def post_comment_reply(comment_id: str):
    """Post short reply under the comment."""
    async with httpx.AsyncClient() as client:
        r = await client.post(
            f"https://graph.instagram.com/{comment_id}/replies",
            params={"access_token": INSTAGRAM_TOKEN},
            json={"message": COMMENT_REPLY},
        )
        return r.json()


async def send_dm(user_id: str, message: str):
    """Send DM with full car details to the commenter."""
    async with httpx.AsyncClient() as client:
        r = await client.post(
            "https://graph.instagram.com/me/messages",
            params={"access_token": INSTAGRAM_TOKEN},
            json={
                "recipient": {"id": user_id},
                "message": {"text": message}
            },
        )
        return r.json()


async def get_comment_user_id(comment_id: str) -> str:
    """Get the Instagram user ID of the commenter."""
    async with httpx.AsyncClient() as client:
        r = await client.get(
            f"https://graph.instagram.com/{comment_id}",
            params={"fields": "id,username,from{id,username}", "access_token": INSTAGRAM_TOKEN},
        )
        data = r.json()
        print(f"Comment data: {data}")
        # Try 'from' field first, then fall back to top-level id
        from_data = data.get("from", {})
        return from_data.get("id", "")


async def already_replied_to_comment(comment_id: str) -> bool:
    """Check if budgetbro007 already replied to this comment."""
    async with httpx.AsyncClient() as client:
        r = await client.get(
            f"https://graph.instagram.com/{comment_id}/replies",
            params={"fields": "username", "access_token": INSTAGRAM_TOKEN},
        )
        for reply in r.json().get("data", []):
            if reply.get("username") == "budgetbro007":
                return True
    return False


async def process_comment(comment_id: str, media_id: str, cars: list, replied: set):
    """Handle a single comment — reply + DM."""
    if comment_id in replied:
        return

    car = next((c for c in cars if c["reel_id"] == media_id and c["active"]), None)
    if not car:
        return

    # Check if we already replied (prevents duplicates on backfill)
    if await already_replied_to_comment(comment_id):
        replied.add(comment_id)
        save_replied(replied)
        return

    # Get commenter's user ID first
    user_id = await get_comment_user_id(comment_id)

    # Post short reply under comment
    reply_result = await post_comment_reply(comment_id)
    print(f"Comment reply result: {reply_result}")

    # Send DM with full details
    if user_id:
        dm_result = await send_dm(user_id, car["reply_text"])
        print(f"DM result: {dm_result}")
    else:
        print("Could not get user ID for DM")

    replied.add(comment_id)
    save_replied(replied)


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
  .btn-backfill { background: #fb8c00; font-size: 12px; padding: 6px 12px; width: auto; margin: 0; border: none; border-radius: 6px; color: white; cursor: pointer; }
  .car-list { display: flex; flex-direction: column; gap: 12px; }
  .car-item { border: 1px solid #eee; border-radius: 10px; padding: 16px; display: flex; justify-content: space-between; align-items: flex-start; gap: 12px; }
  .car-item.inactive { opacity: 0.5; }
  .car-info h3 { font-size: 15px; font-weight: 700; }
  .car-info p { font-size: 13px; color: #666; margin-top: 4px; }
  .reply-preview { font-size: 12px; color: #888; margin-top: 6px; background: #f5f5f5; padding: 8px; border-radius: 6px; }
  .car-actions { display: flex; gap: 8px; flex-shrink: 0; flex-wrap: wrap; justify-content: flex-end; }
  .badge { display: inline-block; padding: 2px 8px; border-radius: 20px; font-size: 11px; font-weight: 700; margin-top: 4px; }
  .badge-on { background: #e8f5e9; color: #2e7d32; }
  .badge-off { background: #fce4ec; color: #b71c1c; }
  .hint { font-size: 12px; color: #888; margin-top: 4px; }
  .empty { text-align: center; color: #aaa; padding: 32px; }
  .info-box { background: #e3f2fd; border-radius: 8px; padding: 12px 16px; margin-bottom: 16px; font-size: 13px; color: #1565c0; }
</style>
</head>
<body>
<div class="header"><span style="font-size:24px">🚗</span><h1>CarBot — Auto Reply Dashboard</h1></div>
<div class="container">

  <div class="card">
    <div class="info-box">💬 When someone comments → Bot replies: <b>"Sent you details on DM 📩"</b> + sends full car details to their DM automatically.</div>
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
        <div><label>DM Message (full details sent to buyer) *</label>
        <textarea name="reply_text" required placeholder="Hi! Thanks for your interest in our Mini Cooper S 🚗&#10;&#10;Details:&#10;Year: 2012&#10;KMs: 41,600&#10;Condition: Excellent, Single Owner&#10;Price: ₹24,99,999&#10;&#10;WhatsApp us for test drive: wa.me/917411946743"></textarea>
        <p class="hint">This is sent as a DM to every person who comments on this reel</p></div>
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
          <p>🔗 <a href="{{ car.reel_url }}" target="_blank" style="color:#1877f2">View Reel</a></p>
          <span class="badge {% if car.active %}badge-on{% else %}badge-off{% endif %}">{% if car.active %}🟢 Active{% else %}🔴 Paused{% endif %}</span>
          <div class="reply-preview">📩 DM: {{ car.reply_text[:120] }}...</div>
        </div>
        <div class="car-actions">
          <form method="POST" action="/cars/{{ car.id }}/backfill"><button class="btn-backfill" type="submit">📬 Reply Old Comments</button></form>
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


@app.post("/cars/{car_id}/backfill")
async def backfill_comments(car_id: int):
    """Fetch all existing comments on the reel and process unresponded ones."""
    cars = load_cars()
    car = next((c for c in cars if c["id"] == car_id), None)
    if not car:
        return RedirectResponse("/", status_code=303)

    replied = load_replied()
    processed = 0

    async with httpx.AsyncClient() as client:
        url = f"https://graph.instagram.com/{car['reel_id']}/comments"
        params = {"fields": "id,text,from", "access_token": INSTAGRAM_TOKEN, "limit": 50}

        while url:
            r = await client.get(url, params=params)
            data = r.json()
            params = {}

            for comment in data.get("data", []):
                comment_id = comment["id"]
                if comment_id not in replied:
                    await process_comment(comment_id, car["reel_id"], cars, replied)
                    processed += 1

            url = data.get("paging", {}).get("next")

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

            if not comment_id:
                continue

            await process_comment(comment_id, media_id, cars, replied)

    return JSONResponse({"status": "ok"})


@app.get("/health")
async def health():
    return {"status": "running", "whatsapp": WHATSAPP}


@app.get("/debug")
async def debug():
    return {"cars": load_cars(), "replied_count": len(load_replied())}


@app.get("/privacy", response_class=HTMLResponse)
async def privacy():
    return "<html><body><h1>Privacy Policy</h1><p>CarBot replies to Instagram comments for BudgetBro Automotive. No personal data stored or shared. Contact: wa.me/917411946743</p></body></html>"
