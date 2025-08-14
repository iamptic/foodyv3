import os, asyncio, asyncpg

DDL_CREATE = [
    """CREATE TABLE IF NOT EXISTS foody_restaurants (
        id TEXT PRIMARY KEY,
        api_key TEXT NOT NULL,
        title TEXT NOT NULL,
        phone TEXT,
        city TEXT,
        address TEXT,
        geo TEXT,
        lat DOUBLE PRECISION,
        lon DOUBLE PRECISION,
        created_at TIMESTAMPTZ DEFAULT NOW()
    )""",
    """CREATE TABLE IF NOT EXISTS foody_offers (
        id TEXT PRIMARY KEY,
        restaurant_id TEXT NOT NULL REFERENCES foody_restaurants(id) ON DELETE CASCADE,
        title TEXT NOT NULL,
        description TEXT,
        price_cents INTEGER NOT NULL,
        original_price_cents INTEGER,
        qty_left INTEGER NOT NULL DEFAULT 0,
        qty_total INTEGER NOT NULL DEFAULT 0,
        expires_at TIMESTAMPTZ,
        archived_at TIMESTAMPTZ,
        photo_url TEXT,
        created_at TIMESTAMPTZ DEFAULT NOW()
    )""",
    """CREATE TABLE IF NOT EXISTS foody_reservations (
        id TEXT PRIMARY KEY,
        offer_id TEXT NOT NULL REFERENCES foody_offers(id) ON DELETE CASCADE,
        code TEXT UNIQUE NOT NULL,
        status TEXT NOT NULL DEFAULT 'reserved',
        created_at TIMESTAMPTZ DEFAULT NOW(),
        redeemed_at TIMESTAMPTZ
    )"""
]

DDL_ALTER = [
    "ALTER TABLE IF EXISTS foody_reservations ADD COLUMN IF NOT EXISTS qty INT NOT NULL DEFAULT 1",
    "ALTER TABLE IF EXISTS foody_restaurants ADD COLUMN IF NOT EXISTS phone TEXT",
    "ALTER TABLE IF EXISTS foody_restaurants ADD COLUMN IF NOT EXISTS city TEXT",
    "ALTER TABLE IF EXISTS foody_restaurants ADD COLUMN IF NOT EXISTS address TEXT",
    "ALTER TABLE IF EXISTS foody_restaurants ADD COLUMN IF NOT EXISTS geo TEXT",
    "ALTER TABLE IF EXISTS foody_restaurants ADD COLUMN IF NOT EXISTS lat DOUBLE PRECISION",
    "ALTER TABLE IF EXISTS foody_restaurants ADD COLUMN IF NOT EXISTS lon DOUBLE PRECISION",
    "ALTER TABLE IF EXISTS foody_offers ADD COLUMN IF NOT EXISTS original_price_cents INTEGER",
    "ALTER TABLE IF EXISTS foody_offers ADD COLUMN IF NOT EXISTS price_cents INTEGER",
    "ALTER TABLE IF EXISTS foody_offers ADD COLUMN IF NOT EXISTS qty_left INTEGER",
    "ALTER TABLE IF EXISTS foody_offers ADD COLUMN IF NOT EXISTS qty_total INTEGER",
    "ALTER TABLE IF EXISTS foody_offers ADD COLUMN IF NOT EXISTS expires_at TIMESTAMPTZ",
    "ALTER TABLE IF EXISTS foody_offers ADD COLUMN IF NOT EXISTS archived_at TIMESTAMPTZ",
    "ALTER TABLE IF EXISTS foody_offers ADD COLUMN IF NOT EXISTS photo_url TEXT"
]

async def run():
    url = os.getenv("DATABASE_URL")
    if not url:
        print("BOOTSTRAP: DATABASE_URL not set, skip migrations")
        return
    try:
        conn = await asyncpg.connect(url)
    except Exception as e:
        print("BOOTSTRAP: Cannot connect to DB:", repr(e))
        return
    try:
        for sql in DDL_CREATE:
            try:
                await conn.execute(sql)
            except Exception as e:
                print("BOOTSTRAP CREATE WARN:", repr(e))
        for sql in DDL_ALTER:
            try:
                await conn.execute(sql)
            except Exception as e:
                print("BOOTSTRAP ALTER WARN:", sql, "->", repr(e))
    finally:
        try:
            await conn.close()
        except Exception:
            pass

async def ensure():
    if os.getenv("RUN_MIGRATIONS", "0").lower() not in ("1","true","yes","on"):
        print("BOOTSTRAP: RUN_MIGRATIONS disabled")
        return
    try:
        await run()
    except Exception as e:
        print("BOOTSTRAP ensure warn:", repr(e))
