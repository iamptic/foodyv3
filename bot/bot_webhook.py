import os
from fastapi import FastAPI, Request, HTTPException
from aiogram import Bot, Dispatcher
from aiogram.enums.parse_mode import ParseMode
from aiogram.client.default import DefaultBotProperties
from aiogram.types import Update, InlineKeyboardMarkup, InlineKeyboardButton, WebAppInfo
from aiogram.filters import CommandStart, Command

BOT_TOKEN = os.getenv("BOT_TOKEN","")
WEBHOOK_SECRET = os.getenv("WEBHOOK_SECRET","foodySecret123")
WEBAPP_PUBLIC = os.getenv("WEBAPP_PUBLIC","https://example.com").rstrip("/")
WEBAPP_BUYER_URL = os.getenv("WEBAPP_BUYER_URL", f"{WEBAPP_PUBLIC}/web/buyer/")
WEBAPP_MERCHANT_URL = os.getenv("WEBAPP_MERCHANT_URL", f"{WEBAPP_PUBLIC}/web/merchant/")

def _https(u:str)->str:
    u = (u or "").strip()
    if u.startswith("http://"): u = "https://" + u[7:]
    if not u.startswith("http"): u = "https://" + u.lstrip('/')
    return u

WEBAPP_BUYER_URL = _https(WEBAPP_BUYER_URL)
WEBAPP_MERCHANT_URL = _https(WEBAPP_MERCHANT_URL)

bot = Bot(BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
dp = Dispatcher()
app = FastAPI()

def kb_main():
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="🛒 Витрина", web_app=WebAppInfo(url=WEBAPP_BUYER_URL)),
        InlineKeyboardButton(text="👨‍🍳 ЛК партнёра", web_app=WebAppInfo(url=WEBAPP_MERCHANT_URL))
    ]])

ABOUT = ("<b>Foody</b> — платформа спасения еды перед закрытием.\n"
         "Рестораны выставляют остатки со скидкой, покупатели забирают рядом и выгодно. 💚")

RULES = ("<b>Правила:</b>\n"
         "• Бронь действует до истечения оффера.\n"
         "• Погашение только в ресторане по QR/коду.\n"
         "• Отмена брони возможна по правилам ресторана.")

GUIDE = ("<b>Как работать:</b>\n"
         "1) Ресторан — зарегистрируйтесь, создайте оффер.\n"
         "2) Покупатель — выберите оффер на витрине и забронируйте.\n"
         "3) На кассе покажите QR/код для погашения.")

@dp.message(CommandStart())
async def on_start(m):
    await m.answer(ABOUT, reply_markup=kb_main())

@dp.message(Command("about"))
async def cmd_about(m): await m.answer(ABOUT)

@dp.message(Command("guide"))
async def cmd_guide(m): await m.answer(GUIDE)

@dp.message(Command("rules"))
async def cmd_rules(m): await m.answer(RULES)

@app.post("/tg/webhook")
async def tg_webhook(request: Request):
    if request.headers.get("x-telegram-bot-api-secret-token") != WEBHOOK_SECRET:
        raise HTTPException(401, "bad secret")
    data = await request.json()
    upd = Update.model_validate(data)
    await dp.feed_update(bot, upd)
    return "OK"

@app.get("/health")
async def health(): return {"ok": True}


@app.post("/tg/notify")
async def tg_notify(request: Request):
    if request.headers.get("x-foody-secret") != WEBHOOK_SECRET:
        raise HTTPException(401, "bad secret")
    data = await request.json()
    text = data.get("text") or "(пусто)"
    # Send to the chat the user most recently used (store in env for MVP)
    chat_id = int(os.getenv("ADMIN_CHAT_ID","0")) if os.getenv("ADMIN_CHAT_ID") else None
    if not chat_id:
        # As a fallback, do nothing (could be extended to a store of restaurant chat ids).
        return {"ok": False, "reason": "no chat configured"}
    await bot.send_message(chat_id, text)
    return {"ok": True}


@dp.message(Command("id"))
async def cmd_id(m): 
    await m.answer(f"Ваш chat_id: <code>{m.chat.id}</code>")
