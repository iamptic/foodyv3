# Minimal aiogram handlers for chat linking (adapt to your bot structure)
from aiogram import Router, F
from aiogram.types import Message
from aiogram.filters import Command

router = Router()

@router.message(Command("id"))
async def cmd_id(msg: Message):
    await msg.answer(f"Ваш chat_id: {msg.chat.id}")

@router.message(Command("link"))
async def cmd_link(msg: Message):
    # Expected: /link ABCDEF  (ABCDEF - one-time code displayed in restaurant LK)
    parts = msg.text.strip().split()
    if len(parts) != 2:
        return await msg.answer("Использование: /link <код>\nПолучите код в личном кабинете ресторана.")
    code = parts[1].strip()
    # TODO: verify the code with backend and bind chat_id to the restaurant:
    # POST {backend}/api/v1/telegram/link  body: { code, chat_id }
    # On success -> backend stores telegram_chat_id in restaurant row
    # Example:
    # async with session.post(f"{BACKEND_URL}/api/v1/telegram/link", json={"code": code, "chat_id": msg.chat.id}) as r:
    #     if r.status == 200: await msg.answer("Чат успешно привязан ✅")
    #     else: await msg.answer("Код не найден или просрочен ❌")
    await msg.answer("(демо) Код принят. Привязка будет выполнена бекендом.")
