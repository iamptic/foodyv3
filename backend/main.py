import os, io, csv, json, secrets, datetime as dt, base64, math, uuid
from typing import Optional, Dict, Any, List

import asyncpg
from fastapi import FastAPI, Header, HTTPException, Query, Body, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse, JSONResponse

import bootstrap_sql
import httpx

DB_URL = os.getenv("DATABASE_URL")

app = FastAPI(title="Foody Backend — MVP+R2")

BOT_NOTIFY_URL = os.getenv('BOT_NOTIFY_URL','').strip()
BOT_NOTIFY_SECRET = os.getenv('BOT_NOTIFY_SECRET','').strip()

origins = [o.strip() for o in os.getenv("CORS_ORIGINS", "").split(",") if o.strip()]
if origins:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

_pool: Optional[asyncpg.pool.Pool] = None
async def pool() -> asyncpg.pool.Pool:
    global _pool
    if _pool is None:
        if not DB_URL:
            raise RuntimeError("DATABASE_URL not set")
        _pool = await asyncpg.create_pool(DB_URL, min_size=1, max_size=5)
    return _pool

def rid() -> str: return "RID_" + secrets.token_hex(4)
def apikey() -> str: return "KEY_" + secrets.token_hex(8)
def offid() -> str: return "OFF_" + secrets.token_hex(6)
def resid() -> str: return "RES_" + secrets.token_hex(6)
def rescode() -> str: return secrets.token_urlsafe(8).upper()

def row_offer(r: asyncpg.Record) -> Dict[str, Any]:
    return {
        "id": r["id"],
        "restaurant_id": r["restaurant_id"],
        "title": r["title"],
        "description": r.get("description"),
        "price_cents": r["price_cents"],
        "original_price_cents": r.get("original_price_cents"),
        "qty_left": r["qty_left"],
        "qty_total": r["qty_total"],
        "expires_at": r["expires_at"].isoformat() if r.get("expires_at") else None,
        "archived_at": r["archived_at"].isoformat() if r.get("archived_at") else None,
        "photo_url": r.get("photo_url"),
        "created_at": r["created_at"].isoformat() if r.get("created_at") else None,
    }

async def auth(conn: asyncpg.Connection, key: str, restaurant_id: Optional[str]) -> str:
    if not key:
        return ""
    if restaurant_id:
        r = await conn.fetchrow("SELECT id FROM foody_restaurants WHERE id=$1 AND api_key=$2", restaurant_id, key)
        return r["id"] if r else ""
    r = await conn.fetchrow("SELECT id FROM foody_restaurants WHERE api_key=$1", key)
    return r["id"] if r else ""

@app.on_event("startup")
async def _startup():
    await bootstrap_sql.ensure()
    try:
        p = await pool()
        async with p.acquire() as conn:
            await seed_if_needed(conn)
    except Exception as e:
        print("Startup seed warn:", repr(e))

@app.middleware("http")
async def guard(request: Request, call_next):
    try:
        return await call_next(request)
    except HTTPException as he:
        raise he
    except Exception as e:
        import traceback; traceback.print_exc()
        return JSONResponse({"detail": "Internal Server Error"}, status_code=500)

@app.get("/health")
async def health():
    try:
        p = await pool()
        async with p.acquire() as conn:
            await conn.execute("SELECT 1")
        return {"ok": True}
    except Exception as e:
        return {"ok": False, "error": str(e)}

# ---- Merchant auth/profile ----

@app.post("/api/v1/merchant/register_public")
async def register_public(raw: Request):
    try:
        if raw.headers.get("content-type","").startswith("application/json"):
            data = await raw.json()
        else:
            txt = await raw.body()
            data = json.loads((txt or b"{}").decode("utf-8"))
    except Exception:
        data = {}
    title = (data.get("title") or "").strip()
    phone = (data.get("phone") or "").strip() or None
    city = (data.get("city") or "").strip() or None
    address = (data.get("address") or "").strip() or None
    geo = (data.get("geo") or "").strip() or None
    lat = float(data.get("lat") or 0) or None
    lon = float(data.get("lon") or 0) or None
    if not title:
        raise HTTPException(422, "title is required")
    p = await pool()
    async with p.acquire() as conn:
        rid_new = rid()
        key_new = apikey()
        await conn.execute(
            "INSERT INTO foody_restaurants(id, api_key, title, phone, city, address, geo, lat, lon) VALUES($1,$2,$3,$4,$5,$6,$7,$8,$9)",
            rid_new, key_new, title, phone, city, address, geo, lat, lon
        )
    return {"restaurant_id": rid_new, "api_key": key_new}

@app.get("/api/v1/merchant/profile")
async def get_profile(restaurant_id: str, x_foody_key: str = Header(default="")):
    p = await pool()
    async with p.acquire() as conn:
        rid_ok = await auth(conn, x_foody_key, restaurant_id)
        if not rid_ok:
            raise HTTPException(401, "Invalid API key or restaurant_id")
        r = await conn.fetchrow("SELECT id, title, phone, city, address, geo, lat, lon FROM foody_restaurants WHERE id=$1", restaurant_id)
        if not r:
            raise HTTPException(404, "Restaurant not found")
        return {"id": r["id"], "title": r["title"], "phone": r["phone"], "city": r["city"], "address": r["address"], "geo": r["geo"], "lat": r["lat"], "lon": r["lon"]}

@app.post("/api/v1/merchant/profile")
async def set_profile(body: Dict[str, Any] = Body(...), x_foody_key: str = Header(default="")):
    rid_in = (body.get("restaurant_id") or "").strip()
    if not rid_in: raise HTTPException(422, "restaurant_id is required")
    title = (body.get("title") or "").strip() or None
    phone = (body.get("phone") or "").strip() or None
    city = (body.get("city") or "").strip() or None
    address = (body.get("address") or "").strip() or None
    geo = (body.get("geo") or "").strip() or None
    lat = body.get("lat"); lat = float(lat) if lat not in (None,"") else None
    lon = body.get("lon"); lon = float(lon) if lon not in (None,"") else None
    p = await pool()
    async with p.acquire() as conn:
        rid_ok = await auth(conn, x_foody_key, rid_in)
        if not rid_ok:
            raise HTTPException(401, "Invalid API key or restaurant_id")
        await conn.execute(
            "UPDATE foody_restaurants SET title=COALESCE($1,title), phone=$2, city=$3, address=$4, geo=$5, lat=$6, lon=$7 WHERE id=$8",
            title, phone, city, address, geo, lat, lon, rid_in
        )
    return {"ok": True}

# ---- Offers CRUD ----

def parse_iso(ts: Optional[str]):
    if not ts: return None
    try:
        return dt.datetime.fromisoformat(ts.replace("Z","+00:00"))
    except Exception:
        raise HTTPException(422, "expires_at must be ISO8601")

@app.get("/api/v1/merchant/offers")
async def merchant_offers(restaurant_id: str, status: Optional[str] = None, x_foody_key: str = Header(default="")):
    p = await pool()
    async with p.acquire() as conn:
        rid_ok = await auth(conn, x_foody_key, restaurant_id)
        if not rid_ok:
            raise HTTPException(401, "Invalid API key or restaurant_id")
        where = ["restaurant_id=$1"]
        params: List[Any] = [restaurant_id]
        if status == "active":
            where += ["(archived_at IS NULL)", "(expires_at IS NULL OR expires_at > NOW())", "(qty_left IS NULL OR qty_left > 0)"]
        sql = f"SELECT * FROM foody_offers WHERE {' AND '.join(where)} ORDER BY created_at DESC"
        rows = await conn.fetch(sql, *params)
        return [row_offer(r) for r in rows]

@app.post("/api/v1/merchant/offers")
async def create_offer(body: Dict[str, Any] = Body(...), x_foody_key: str = Header(default="")):
    rid_in = (body.get("restaurant_id") or "").strip()
    p = await pool()
    async with p.acquire() as conn:
        rid_ok = await auth(conn, x_foody_key, rid_in)
        if not rid_ok:
            raise HTTPException(401, "Invalid API key or restaurant_id")
        oid = offid()
        title = (body.get("title") or "").strip()
        if not title: raise HTTPException(422, "title is required")
        # prices in RUB accepted -> convert to cents if <= 100000
        def to_cents(v):
            if v is None or v == "": return None
            v = float(v)
            return int(round(v*100)) if v < 100000 else int(v)
        price_cents = to_cents(body.get("price") if "price" in body else body.get("price_cents"))
        original_price_cents = to_cents(body.get("original_price") if "original_price" in body else body.get("original_price_cents"))
        if price_cents is None: raise HTTPException(422, "price/price_cents is required")
        qty_total = int(body.get("qty_total") or body.get("qty") or 0)
        qty_left = int(body.get("qty_left") or qty_total)
        expires_ts = parse_iso(body.get("expires_at"))
        photo_url = (body.get("photo_url") or "").strip() or None
        await conn.execute(
            """INSERT INTO foody_offers(id, restaurant_id, title, description, price_cents, original_price_cents,
                                        qty_left, qty_total, expires_at, photo_url)
               VALUES($1,$2,$3,$4,$5,$6,$7,$8,$9,$10)""",
            oid, rid_in, title, (body.get("description") or None), price_cents, original_price_cents, qty_left, qty_total, expires_ts, photo_url
        )
        r = await conn.fetchrow("SELECT * FROM foody_offers WHERE id=$1", oid)
        return row_offer(r)

@app.post("/api/v1/merchant/offers/{offer_id}")
async def edit_offer(offer_id: str, body: Dict[str, Any] = Body(...), x_foody_key: str = Header(default="")):
    rid_in = (body.get("restaurant_id") or "").strip()
    p = await pool()
    async with p.acquire() as conn:
        rid_ok = await auth(conn, x_foody_key, rid_in)
        if not rid_ok:
            raise HTTPException(401, "Invalid API key or restaurant_id")
        fields = []
        vals: List[Any] = []
        def setf(name, val):
            nonlocal fields, vals
            fields.append(f"{name}=${len(vals)+1}"); vals.append(val)
        if "title" in body: setf("title", (body.get("title") or "").strip())
        if "description" in body: setf("description", (body.get("description") or None))
        if "price" in body or "price_cents" in body:
            v = float(body.get("price") or body.get("price_cents") or 0)
            setf("price_cents", int(round(v*100)) if v < 100000 else int(v))
        if "original_price" in body or "original_price_cents" in body:
            v = body.get("original_price") or body.get("original_price_cents")
            if v not in (None,""):
                v = float(v); setf("original_price_cents", int(round(v*100)) if v < 100000 else int(v))
        if "qty_total" in body: setf("qty_total", int(body.get("qty_total")))
        if "qty_left" in body: setf("qty_left", int(body.get("qty_left")))
        if "expires_at" in body: setf("expires_at", parse_iso(body.get("expires_at")))
        if "photo_url" in body: setf("photo_url", (body.get("photo_url") or None))
        if not fields: return {"ok": True}
        vals += [offer_id]
        await conn.execute(f"UPDATE foody_offers SET {', '.join(fields)} WHERE id=${len(vals)}", *vals)
        r = await conn.fetchrow("SELECT * FROM foody_offers WHERE id=$1", offer_id)
        return row_offer(r)

@app.delete("/api/v1/merchant/offers/{offer_id}")
async def delete_offer(offer_id: str, restaurant_id: Optional[str] = None, x_foody_key: str = Header(default="")):
    p = await pool()
    async with p.acquire() as conn:
        rid_ok = await auth(conn, x_foody_key, restaurant_id)
        if not rid_ok: raise HTTPException(401, "Invalid API key or restaurant_id")
        chk = await conn.fetchrow("SELECT id, restaurant_id FROM foody_offers WHERE id=$1", offer_id)
        if not chk: raise HTTPException(404, "Offer not found")
        if restaurant_id and chk["restaurant_id"] != restaurant_id: raise HTTPException(403, "Offer belongs to another restaurant")
        await conn.execute("UPDATE foody_offers SET archived_at=NOW() WHERE id=$1", offer_id)
        return {"ok": True, "deleted": offer_id}

# ---- Offers public with sorting and discount ----

def with_timer_discount(r: Dict[str, Any]) -> Dict[str, Any]:
    out = dict(r)
    now = dt.datetime.utcnow().replace(tzinfo=dt.timezone.utc)
    expires_at = None
    if r["expires_at"]:
        try: expires_at = dt.datetime.fromisoformat(r["expires_at"].replace("Z","+00:00"))
        except Exception: expires_at = None
    discount_percent = 0; step = None
    if expires_at:
        delta = (expires_at - now).total_seconds() / 60.0
        if delta <= 30: discount_percent=70; step="-70%"
        elif delta <= 60: discount_percent=50; step="-50%"
        elif delta <= 120: discount_percent=30; step="-30%"
    original = r.get("original_price_cents") or r.get("price_cents")
    current = r.get("price_cents")
    if (original and original>0) and discount_percent>0:
        current = int(round(original * (1 - discount_percent/100)))
    out["timer_discount_percent"] = discount_percent
    out["timer_step"] = step
    out["price_cents_effective"] = current
    return out

def haversine_km(lat1, lon1, lat2, lon2):
    R=6371.0
    from math import radians, sin, cos, sqrt, asin
    φ1, λ1, φ2, λ2 = map(radians, [lat1,lon1,lat2,lon2])
    dφ = φ2-φ1; dλ = λ2-λ1
    a = sin(dφ/2)**2 + cos(φ1)*cos(φ2)*sin(dλ/2)**2
    c = 2*asin(sqrt(a))
    return R*c

@app.get("/api/v1/offers")
async def public_offers(limit: int = Query(200, ge=1, le=500), sort: str = "expiry",
                        lat: Optional[float] = None, lon: Optional[float] = None, city: Optional[str] = None):
    p = await pool()
    async with p.acquire() as conn:
        rows = await conn.fetch(
            """SELECT o.*, r.lat as rlat, r.lon as rlon, r.city as rcity FROM foody_offers o
               JOIN foody_restaurants r ON r.id=o.restaurant_id
               WHERE (o.archived_at IS NULL)
                 AND (o.expires_at IS NULL OR o.expires_at > NOW())
                 AND (o.qty_left IS NULL OR o.qty_left > 0)
               ORDER BY o.expires_at NULLS LAST, o.id
               LIMIT $1""", limit
        )
        base = [row_offer(r) for r in rows]
        base = [with_timer_discount(o) for o in base]
        # attach distance if lat/lon present
        enriched = []
        for r,raw in zip(base, rows):
            d=None
            if lat is not None and lon is not None and raw["rlat"] and raw["rlon"]:
                d = haversine_km(lat, lon, raw["rlat"], raw["rlon"])
            r["distance_km"]=d
            r["city"]=raw["rcity"]
            enriched.append(r)
        if city:
            enriched = [e for e in enriched if (e.get("city") or "").lower()==city.lower()]
        if sort=="price":
            enriched.sort(key=lambda x: (x.get("price_cents_effective") or x.get("price_cents") or 10**12))
        elif sort=="new":
            enriched.sort(key=lambda x: x.get("created_at") or "", reverse=True)
        elif sort=="distance" and lat is not None and lon is not None:
            enriched.sort(key=lambda x: (x.get("distance_km") if x.get("distance_km") is not None else 10**6))
        else: # expiry default
            def eta(o):
                if not o.get("expires_at"): return 10**12
                try:
                    t = dt.datetime.fromisoformat(o["expires_at"].replace("Z","+00:00"))
                except Exception:
                    return 10**12
                return (t - dt.datetime.utcnow().replace(tzinfo=dt.timezone.utc)).total_seconds()
            enriched.sort(key=lambda x: eta(x))
        return enriched

# ---- CSV ----
@app.get("/api/v1/merchant/offers/csv")
async def export_csv(restaurant_id: str):
    p = await pool()
    async with p.acquire() as conn:
        rows = await conn.fetch("SELECT * FROM foody_offers WHERE restaurant_id=$1 ORDER BY created_at", restaurant_id)
    def gen():
        buf = io.StringIO()
        w = csv.writer(buf)
        w.writerow(["id","restaurant_id","title","description","price_cents","original_price_cents","qty_left","qty_total","expires_at","archived_at","photo_url","created_at"])
        for r in rows:
            w.writerow([
                r["id"], r["restaurant_id"], r["title"], r.get("description") or "",
                r["price_cents"], r.get("original_price_cents") or "",
                r["qty_left"], r["qty_total"],
                r["expires_at"].isoformat() if r.get("expires_at") else "",
                r["archived_at"].isoformat() if r.get("archived_at") else "",
                r.get("photo_url") or "",
                r["created_at"].isoformat() if r.get("created_at") else "",
            ])
        yield buf.getvalue()
    return StreamingResponse(gen(), media_type="text/csv",
                             headers={"Content-Disposition": f"attachment; filename=offers_{restaurant_id}.csv"})

# ---- Reservations + QR ----
def make_qr_png_b64(text: str) -> str:
    import qrcode
    from io import BytesIO
    img = qrcode.make(text)
    bio = BytesIO()
    img.save(bio, format="PNG")
    return base64.b64encode(bio.getvalue()).decode("ascii")

@app.post("/api/v1/reservations")
async def create_reservation(body: Dict[str, Any] = Body(...)):
    offer_id = (body.get("offer_id") or "").strip()
    if not offer_id: raise HTTPException(422, "offer_id required")
    qty = int(body.get("qty") or 1)
    if qty < 1: raise HTTPException(422, "qty must be >= 1")
    p = await pool()
    async with p.acquire() as conn:
        off = await conn.fetchrow("SELECT id, qty_left FROM foody_offers WHERE id=$1 AND (archived_at IS NULL) AND (expires_at IS NULL OR expires_at>NOW())", offer_id)
        if not off: raise HTTPException(404, "Offer not found or inactive")
        if off["qty_left"] is not None and off["qty_left"] < qty: raise HTTPException(409, "Not enough items left")
        code = rescode()
        rid = resid()
        async with conn.transaction():
            await conn.execute("INSERT INTO foody_reservations(id, offer_id, code, status, qty) VALUES($1,$2,$3,'reserved',$4)", rid, offer_id, code, qty)
            if off["qty_left"] is not None:
                await conn.execute("UPDATE foody_offers SET qty_left=qty_left-$1 WHERE id=$2", qty, offer_id)
    qr_b64 = make_qr_png_b64(code)
    return {"id": rid, "code": code, "qty": qty, "qrcode_png_base64": qr_b64}

@app.post("/api/v1/reservations/redeem")
async def redeem_reservation(body: Dict[str, Any] = Body(...), x_foody_key: str = Header(default="")):
    code = (body.get("code") or "").strip()
    if not code: raise HTTPException(422, "code required")
    p = await pool()
    async with p.acquire() as conn:
        res = await conn.fetchrow("""SELECT r.*, o.restaurant_id FROM foody_reservations r 
                                     JOIN foody_offers o ON o.id=r.offer_id WHERE r.code=$1""", code)
        if not res: raise HTTPException(404, "Reservation not found")
        # ensure merchant key matches the offer's restaurant
        rid_ok = await auth(conn, x_foody_key, res["restaurant_id"])
        if not rid_ok: raise HTTPException(401, "Invalid merchant key for this reservation")
        if res["status"] == "redeemed": return {"ok": True, "status": "already_redeemed"}
        await conn.execute("UPDATE foody_reservations SET status='redeemed', redeemed_at=NOW() WHERE id=$1", res["id"])
        return {"ok": True, "status": "redeemed"}

@app.post("/api/v1/reservations/cancel")
async def cancel_reservation(body: Dict[str, Any] = Body(...)):
    code = (body.get("code") or "").strip()
    if not code: raise HTTPException(422, "code required")
    p = await pool()
    async with p.acquire() as conn:
        res = await conn.fetchrow("""SELECT r.*, o.expires_at, o.id as oid FROM foody_reservations r
                                     JOIN foody_offers o ON o.id=r.offer_id WHERE r.code=$1""", code)
        if not res: raise HTTPException(404, "Reservation not found")
        if res["status"] != "reserved":
            return {"ok": False, "status": res["status"]}
        if res["expires_at"] and res["expires_at"] < dt.datetime.utcnow().replace(tzinfo=dt.timezone.utc):
            return {"ok": False, "status": "expired"}
        async with conn.transaction():
            await conn.execute("UPDATE foody_reservations SET status='canceled' WHERE id=$1", res["id"])
            await conn.execute("UPDATE foody_offers SET qty_left=qty_left+$1 WHERE id=$2", res["qty"], res["oid"])
        return {"ok": True, "status": "canceled"}


# ---- KPI stub ----
@app.get("/api/v1/merchant/kpi")
async def kpi(restaurant_id: str, x_foody_key: str = Header(default="")):
    p = await pool()
    async with p.acquire() as conn:
        rid_ok = await auth(conn, x_foody_key, restaurant_id)
        if not rid_ok:
            raise HTTPException(401, "Invalid API key or restaurant_id")
        reserved = await conn.fetchval("""SELECT COUNT(*) FROM foody_reservations r 
                                          JOIN foody_offers o ON o.id=r.offer_id 
                                          WHERE o.restaurant_id=$1""", restaurant_id)
        redeemed = await conn.fetchval("""SELECT COUNT(*) FROM foody_reservations r 
                                          JOIN foody_offers o ON o.id=r.offer_id 
                                          WHERE o.restaurant_id=$1 AND r.status='redeemed'""", restaurant_id)
        revenue = await conn.fetchval("""SELECT COALESCE(SUM(o.price_cents),0) FROM foody_reservations r 
                                         JOIN foody_offers o ON o.id=r.offer_id 
                                         WHERE o.restaurant_id=$1 AND r.status='redeemed'""", restaurant_id)
        rate = (redeemed / reserved) if reserved else 0.0
        return {"reserved": reserved, "redeemed": redeemed, "redemption_rate": round(rate,2), "revenue_cents": int(revenue or 0), "saved_cents": 0}

# ---- R2 presigned uploads ----
import boto3
R2_ENDPOINT = os.getenv("R2_ENDPOINT","").rstrip("/")
R2_BUCKET = os.getenv("R2_BUCKET","")
R2_ACCESS_KEY_ID = os.getenv("R2_ACCESS_KEY_ID","")
R2_SECRET_ACCESS_KEY = os.getenv("R2_SECRET_ACCESS_KEY","")

def _r2_client():
    if not (R2_ENDPOINT and R2_BUCKET and R2_ACCESS_KEY_ID and R2_SECRET_ACCESS_KEY):
        raise HTTPException(400, "R2 is not configured")
    return boto3.client("s3", endpoint_url=R2_ENDPOINT, aws_access_key_id=R2_ACCESS_KEY_ID,
                        aws_secret_access_key=R2_SECRET_ACCESS_KEY, region_name="auto")

@app.post("/api/v1/uploads/presign")
async def presign_upload(params: Dict[str, Any] = Body(...)):
    filename = (params.get("filename") or "upload.bin")
    content_type = (params.get("content_type") or "application/octet-stream")
    ext = ""
    if "." in filename:
        ext = filename.rsplit(".",1)[-1].lower()
        if len(ext) > 8: ext = ""
    key = f"offers/{uuid.uuid4().hex}{('.'+ext) if ext else ''}"
    try:
        s3 = _r2_client()
        put_url = s3.generate_presigned_url(
            "put_object",
            Params={"Bucket": R2_BUCKET, "Key": key, "ContentType": content_type},
            ExpiresIn=3600
        )
        public_url = f"{R2_ENDPOINT}/{R2_BUCKET}/{key}"
        return {"put_url": put_url, "public_url": public_url, "key": key}
    except Exception as e:
        raise HTTPException(500, f"Cannot presign: {e}")

# ---- Seed ----
TEST_RID = "RID_TEST"
TEST_KEY = "KEY_TEST"

async def seed_if_needed(conn: asyncpg.Connection):
    cnt = await conn.fetchval("SELECT COUNT(*) FROM foody_restaurants")
    has_test = await conn.fetchrow("SELECT id FROM foody_restaurants WHERE id=$1", TEST_RID)
    if cnt and has_test: return
    if cnt and not has_test:
        try: await conn.execute("TRUNCATE foody_reservations RESTART IDENTITY CASCADE")
        except Exception: pass
        try: await conn.execute("TRUNCATE foody_offers RESTART IDENTITY CASCADE")
        except Exception: pass
        try: await conn.execute("TRUNCATE foody_restaurants RESTART IDENTITY CASCADE")
        except Exception: pass
    await conn.execute(
        "INSERT INTO foody_restaurants(id, api_key, title, phone, city, address, geo, lat, lon) VALUES($1,$2,$3,$4,$5,$6,$7,$8,$9)",
        TEST_RID, TEST_KEY, "Пекарня №1", "+7 900 000-00-00", "Москва", "ул. Пекарная, 10", "55.7558,37.6173", 55.7558, 37.6173
    )
    now = dt.datetime.utcnow().replace(tzinfo=dt.timezone.utc)
    def exp(minutes): return now + dt.timedelta(minutes=minutes)
    demo = [
        ("Эклеры", "Набор свежих эклеров", 19900, 34900, 5, 5, exp(110), None),
        ("Пирожки", "Пирожки с мясом", 14900, 29900, 8, 8, exp(55), None),
        ("Круассаны", "Круассаны с маслом", 9900, 32900, 6, 6, exp(25), None),
    ]
    for title, desc, price, orig, qty_left, qty_total, expires, photo in demo:
        await conn.execute(
            """INSERT INTO foody_offers(id, restaurant_id, title, description, price_cents, original_price_cents,
                                        qty_left, qty_total, expires_at, photo_url)
               VALUES($1,$2,$3,$4,$5,$6,$7,$8,$9,$10)""",
            offid(), TEST_RID, title, desc, price, orig, qty_left, qty_total, expires, photo
        )

# uvicorn main:app --host 0.0.0.0 --port 8080

@app.get("/api/v1/reservations/qr")
async def reservation_qr(code: str):
    if not code: raise HTTPException(422, "code required")
    return {"qrcode_png_base64": make_qr_png_b64(code)}

# === DEV-ONLY merchant recovery by phone (guarded by RECOVERY_SECRET) ===
@app.post("/api/v1/merchant/recover")
async def merchant_recover(body: Dict[str, Any] = Body(...)):
    secret = os.getenv("RECOVERY_SECRET", "")
    if not secret:
        raise HTTPException(503, "Recovery is not enabled")
    if (body.get("secret") or "") != secret:
        raise HTTPException(403, "Forbidden")
    phone = (body.get("phone") or "").strip()
    if not phone:
        raise HTTPException(422, "phone required")
    p = await pool()
    async with p.acquire() as conn:
        r = await conn.fetchrow("SELECT id, api_key, title FROM foody_restaurants WHERE phone=$1 ORDER BY created_at DESC LIMIT 1", phone)
        if not r:
            raise HTTPException(404, "Not found")
        return {"restaurant_id": r["id"], "api_key": r["api_key"], "title": r["title"]}


# === DEV-ONLY merchant recovery by phone (guarded by RECOVERY_SECRET) ===
from typing import Any, Dict
import os as _os
import datetime as _dt

@app.post("/api/v1/merchant/recover")
async def merchant_recover(body: Dict[str, Any] = Body(...)):
    secret = _os.getenv("RECOVERY_SECRET", "")
    if not secret:
        raise HTTPException(503, "Recovery is not enabled")
    if (body.get("secret") or "") != secret:
        raise HTTPException(403, "Forbidden")
    phone = (body.get("phone") or "").strip()
    if not phone:
        raise HTTPException(422, "phone required")
    p = await pool()
    async with p.acquire() as conn:
        r = await conn.fetchrow("SELECT id, api_key, title FROM foody_restaurants WHERE phone=$1 ORDER BY created_at DESC LIMIT 1", phone)
        if not r:
            raise HTTPException(404, "Not found")
        return {"restaurant_id": r["id"], "api_key": r["api_key"], "title": r["title"]}

# ---- Reservations + QR ----
def make_qr_png_b64(text: str) -> str:
    # Minimal inline QR using segno if available, else a tiny placeholder
    try:
        import base64, io, segno
        buf = io.BytesIO()
        segno.make(text, micro=False).save(buf, kind="png", scale=5)
        return base64.b64encode(buf.getvalue()).decode("ascii")
    except Exception:
        # Fallback: return a tiny 1x1 png
        import base64
        return "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR4nGMAAQAABQABDQottAAAAABJRU5ErkJggg=="

@app.get("/api/v1/reservations/qr")
async def reservation_qr(code: str):
    if not code:
        raise HTTPException(422, "code required")
    return {"qrcode_png_base64": make_qr_png_b64(code)}

@app.post('/internal/notify')
async def internal_notify(body: Dict[str, Any] = Body(...)):
    # Placeholder: accept notifications from backend to bot or elsewhere.
    # For MVP this is a no-op, just logs input and returns ok.
    return {'ok': True}


async def notify_bot(text: str):
    if not BOT_NOTIFY_URL: return
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            headers = {'x-foody-secret': BOT_NOTIFY_SECRET} if BOT_NOTIFY_SECRET else {}
            await client.post(BOT_NOTIFY_URL, headers=headers, json={'text': text})
    except Exception as e:
        print("notify_bot warn:", repr(e))