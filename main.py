from fastapi import FastAPI, Request, Form
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse, PlainTextResponse
import httpx
import os
import re
import psycopg2
from psycopg2.extras import RealDictCursor

INSTAGRAM_TOKEN = os.environ.get("INSTAGRAM_TOKEN", "IGAASawBMiF8hBZAFlQdmxEUDVTZA3loN256TU51Tmo4eVQ5UUVXZAXJjNExTTnlUWjZA4ZA2tZAc3lfbXRGMTFMR3BaV1BuZAGFYQmNnMHllQkpBNGROMWFaWHlkVFFnQkQxeGd0ZAGxGVWVZAanJSeEl1S1hMRzZAlZAnRZAQ3NpT252Q01wOAZDZD")
WHATSAPP = os.environ.get("WHATSAPP", "917411946743")
VERIFY_TOKEN = os.environ.get("VERIFY_TOKEN", "carbot_verify_2024")
DATABASE_URL = os.environ.get("DATABASE_URL", "postgresql://carbot_db_user:OyGxR3myv0WjFCrido8Ndjw3Fi9vyAH5@dpg-d8ggit58nd3s738vmn90-a/carbot_db")

app = FastAPI()
COMMENT_REPLY = "Thanks for your interest! 😊 We've sent you the full details on DM — please check! 📩"


def get_db():
    return psycopg2.connect(DATABASE_URL, cursor_factory=RealDictCursor)


def init_db():
    conn = get_db()
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS cars (
            id SERIAL PRIMARY KEY,
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
    cur.execute("""
        CREATE TABLE IF NOT EXISTS replied_comments (
            comment_id TEXT PRIMARY KEY,
            replied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.commit()
    cur.close()
    conn.close()


init_db()


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
    async with httpx.AsyncClient() as client:
        r = await client.post(
            f"https://graph.instagram.com/{comment_id}/replies",
            params={"access_token": INSTAGRAM_TOKEN},
            json={"message": COMMENT_REPLY},
        )
        return r.json()


async def send_dm(user_id: str, message: str):
    async with httpx.AsyncClient() as client:
        r = await client.post(
            "https://graph.instagram.com/me/messages",
            params={"access_token": INSTAGRAM_TOKEN},
            json={"recipient": {"id": user_id}, "message": {"text": message}},
        )
        return r.json()


async def get_comment_user_id(comment_id: str) -> str:
    async with httpx.AsyncClient() as client:
        r = await client.get(
            f"https://graph.instagram.com/{comment_id}",
            params={"fields": "id,from{id,username}", "access_token": INSTAGRAM_TOKEN},
        )
        data = r.json()
        print(f"Comment data: {data}")
        return data.get("from", {}).get("id", "")


async def already_replied(comment_id: str) -> bool:
    async with httpx.AsyncClient() as client:
        r = await client.get(
            f"https://graph.instagram.com/{comment_id}/replies",
            params={"fields": "username", "access_token": INSTAGRAM_TOKEN},
        )
        for reply in r.json().get("data", []):
            if reply.get("username") == "budgetbro007":
                return True
    return False


def is_replied_in_db(comment_id: str) -> bool:
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT 1 FROM replied_comments WHERE comment_id = %s", (comment_id,))
    result = cur.fetchone()
    cur.close()
    conn.close()
    return result is not None


def mark_replied(comment_id: str):
    conn = get_db()
    cur = conn.cursor()
    cur.execute("INSERT INTO replied_comments (comment_id) VALUES (%s) ON CONFLICT DO NOTHING", (comment_id,))
    conn.commit()
    cur.close()
    conn.close()


async def process_comment(comment_id: str, media_id: str):
    if is_replied_in_db(comment_id):
        return

    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT * FROM cars WHERE reel_id = %s AND active = 1", (media_id,))
    car = cur.fetchone()
    cur.close()
    conn.close()

    if not car:
        print(f"No active car for media_id={media_id}")
        return

    if await already_replied(comment_id):
        mark_replied(comment_id)
        return

    user_id = await get_comment_user_id(comment_id)

    reply_result = await post_comment_reply(comment_id)
    print(f"Comment reply: {reply_result}")

    if user_id:
        dm_result = await send_dm(user_id, car["reply_text"])
        print(f"DM result: {dm_result}")
    else:
        print("Could not get user_id for DM")

    mark_replied(comment_id)


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
        <div><label>DM Message (sent to every commenter) *</label>
        <textarea name="reply_text" required placeholder="Hi! Thanks for your interest 🚗&#10;&#10;Car: Mini Cooper S&#10;Year: 2012 | KMs: 41,600&#10;Condition: Excellent, Single Owner&#10;Price: ₹24,99,999&#10;&#10;WhatsApp for test drive: wa.me/917411946743"></textarea>
        <p class="hint">This is sent as a DM to every person who comments</p></div>
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
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT * FROM cars ORDER BY created_at DESC")
    cars = cur.fetchall()
    cur.close()
    conn.close()
    from jinja2 import Template
    return Template(DASHBOARD_HTML).render(cars=[dict(c) for c in cars])


@app.post("/cars")
async def add_car(
    car_name: str = Form(...), price: str = Form(...), year: str = Form(""),
    km: str = Form(""), condition: str = Form(""), reel_url: str = Form(...), reply_text: str = Form(...),
):
    shortcode = extract_reel_shortcode(reel_url)
    media_id = await get_media_id_from_shortcode(shortcode) if shortcode else reel_url
    conn = get_db()
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO cars (reel_id, reel_url, car_name, price, year, km, condition, reply_text) VALUES (%s,%s,%s,%s,%s,%s,%s,%s)",
        (media_id, reel_url, car_name, price, year, km, condition, reply_text),
    )
    conn.commit()
    cur.close()
    conn.close()
    return RedirectResponse("/", status_code=303)


@app.post("/cars/{car_id}/toggle")
async def toggle_car(car_id: int):
    conn = get_db()
    cur = conn.cursor()
    cur.execute("UPDATE cars SET active = 1 - active WHERE id = %s", (car_id,))
    conn.commit()
    cur.close()
    conn.close()
    return RedirectResponse("/", status_code=303)


@app.post("/cars/{car_id}/delete")
async def delete_car(car_id: int):
    conn = get_db()
    cur = conn.cursor()
    cur.execute("DELETE FROM cars WHERE id = %s", (car_id,))
    conn.commit()
    cur.close()
    conn.close()
    return RedirectResponse("/", status_code=303)


@app.post("/cars/{car_id}/backfill")
async def backfill_comments(car_id: int):
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT * FROM cars WHERE id = %s", (car_id,))
    car = cur.fetchone()
    cur.close()
    conn.close()
    if not car:
        return RedirectResponse("/", status_code=303)

    async with httpx.AsyncClient() as client:
        url = f"https://graph.instagram.com/{car['reel_id']}/comments"
        params = {"fields": "id,text", "access_token": INSTAGRAM_TOKEN, "limit": 50}
        while url:
            r = await client.get(url, params=params)
            data = r.json()
            params = {}
            for comment in data.get("data", []):
                await process_comment(comment["id"], car["reel_id"])
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
    for entry in body.get("entry", []):
        for change in entry.get("changes", []):
            if change.get("field") != "comments":
                continue
            value = change.get("value", {})
            comment_id = value.get("id")
            media_id = value.get("media", {}).get("id", "")
            print(f"comment={comment_id} media={media_id}")
            if comment_id:
                await process_comment(comment_id, media_id)
    return JSONResponse({"status": "ok"})


@app.get("/health")
async def health():
    return {"status": "running", "whatsapp": WHATSAPP}


@app.get("/debug")
async def debug():
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT id, reel_id, car_name, active FROM cars")
    cars = cur.fetchall()
    cur.execute("SELECT COUNT(*) as cnt FROM replied_comments")
    count = cur.fetchone()
    cur.close()
    conn.close()
    return {"cars": [dict(c) for c in cars], "replied_count": count["cnt"]}


@app.get("/privacy", response_class=HTMLResponse)
async def privacy():
    return "<html><body><h1>Privacy Policy</h1><p>CarBot replies to Instagram comments for BudgetBro Automotive. No personal data stored or shared. Contact: wa.me/917411946743</p></body></html>"
