# Foody — Canvas Release

Версия: canvas-1755135041

## Развёртывание (Railway)

### backend
- Root: `backend`
- Start: `uvicorn main:app --host 0.0.0.0 --port 8080`
- ENV:
  - `DATABASE_URL=...`
  - `RUN_MIGRATIONS=1`
  - `CORS_ORIGINS=https://web-production-5431c.up.railway.app,https://bot-production-0297.up.railway.app`
  - `R2_ENDPOINT=https://c1892812feb332b56b53f2f36d14e95f.r2.cloudflarestorage.com`
  - `R2_BUCKET=foody`
  - `R2_ACCESS_KEY_ID=...`
  - `R2_SECRET_ACCESS_KEY=...`
  - `RECOVERY_SECRET=foodyDevRecover123`

### web
- Root: `web`
- Start: `node server.js`
- ENV:
  - `FOODY_API=https://<backend-domain>`

### bot
- Root: `bot`
- Start: `uvicorn bot_webhook:app --host 0.0.0.0 --port 8080`
- ENV:
  - `BOT_TOKEN=...`
  - `WEBHOOK_SECRET=foodySecret123`
  - `WEBAPP_PUBLIC=https://web-production-5431c.up.railway.app`

### No-cache
- В `web/server.js` добавлены заголовки `Cache-Control: no-store` для HTML и `/config.js`.
- В шапке buyer/merchant виден бейдж версии (комментарий `FOODY_BUILD_VERSION`).

## Быстрый тест
1. Открой `/web/merchant/` → регистрация ресторана → авто-вход.
2. Загрузите фото (R2) → создайте оффер.
3. Откройте `/web/buyer/` → бронь (qty) → история броней → QR/отмена.
4. Сортировки: цена, новинки, ближе; карта с маркерами.

Удачного запуска! 🚀
