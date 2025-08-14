# Foody Hotfix Overlay: Web Proxy, Health, and Bot Chat Linking

This overlay provides:
- **Web**: `server.js` to run on Railway and proxy `/api` -> `BACKEND_URL`.
- **Backend**: health/ready endpoints and integration snippet + CORS example.
- **Bot**: `/id` and `/link` handlers for chat binding + backend linking spec.

## How to apply
1. Copy files into your repo respecting paths:   - `web/server.js`, `web/package.json.additions.json`, `web/vite.config.dev-proxy.snippet.ts`, `web/.env.example`   - `backend/app/health_endpoints.py`, `backend/app/MAIN_INTEGRATION_SNIPPET.py`, `backend/.env.example`   - `backend/app/telegram_link_endpoint.py`   - `bot/chat_link_handlers.py`, `bot/.env.example`
2. In **web/package.json**, add:
```json
"scripts": { "build": "vite build", "start": "node server.js", "dev": "vite" },
"dependencies": { "express": "^4.19.2", "http-proxy-middleware": "^3.0.0" }
```
3. Rebuild web on Railway:
   - Add variable `BACKEND_URL=https://backend-production-a417.up.railway.app`
   - Start command should be `npm run start` (after build step).
4. Backend:
   - Include routers and health endpoints in `main.py`:
```py
from app.health_endpoints import router as health_router
from app.telegram_link_endpoint import router as tg_link_router
app.include_router(health_router)
app.include_router(tg_link_router)
```
   - Ensure business routers have `/api` or `/api/v1` prefix aligned with frontend.
5. Bot:
   - Register `chat_link_handlers.router` in your bot setup.
   - Ensure `BACKEND_URL` is set for calling `/api/v1/telegram/link` on link.
6. Smoke tests:
```bash
# health
curl -s https://backend-production-a417.up.railway.app/health
# registration/login (adjust URL to your actual route)
curl -i -X POST https://web-production-5431c.up.railway.app/api/auth/register -H 'content-type: application/json' -d '{}'
# reserve flow (adjust endpoints accordingly)
# bot: /id and /link ABCDEF (code from LK) -> expect success
```

## Notes
- If your backend does NOT expose `/api` prefix internally, enable `pathRewrite` in `server.js` or `rewrite` in Vite dev proxy.
- Lock down CORS `allow_origins` to your web domain in prod.
- Consider adding `/ready` db checks and structured logging with request_id.
