# AGENTS.md

## Project

Solo Leveling Hunter RPG is a Telegram bot with a companion Mini App for hunter status, daily claims, shop purchases, and read-only guild browsing.

- Bot and API: Python 3.11+, Kurigram, FastAPI/Uvicorn.
- Mini App: static TypeScript, React, and Vite; host the frontend on Vercel or GitHub Pages.
- Persistent game data: private Telegram channels only. `channel_db.py` and `shadows_db.py` store JSON messages; do not add another game database.
- Visual language: preserve Hallmark design tokens and accessible contrast in bot cards and the Mini App.

## Boundaries and conventions

- The FastAPI app in `miniapp_api.py` runs in the bot process and uses its initialized Telegram client and `ChannelDB` cache. Keep the API on the always-on bot host; deploy only the static frontend to Vercel/Pages.
- Send raw `Telegram.WebApp.initData` to the API. Validate its HMAC with server-side `BOT_TOKEN`, reject data older than 24 hours or more than 30 seconds in the future, and derive the user ID only from the validated payload. Never trust `initDataUnsafe`, caller-supplied IDs, or frontend secrets; never expose `BOT_TOKEN` in `VITE_*` variables.
- Claim and shop use the shared locked operations in `game/economy.py` from both bot handlers and API routes. Telegram records are separate messages, so compensating saves cannot guarantee atomic writes. A `storage_error` may mean a partial or uncertain write: check balance and inventory, then contact a bot admin before retrying. Shop request deduplication is in-process only.
- Mini App guild browsing is read-only. Guild creation, membership, and management stay in bot commands.
- Bot text uses `telegram-text` via `game/rich_text.py`: escape dynamic HTML before wrapping it and call `.to_html()` on formatter elements. Build rich documents with `game/rich_message.py`; send via `game/rich_send.py` to retain classic-message fallback behavior.
- Use only semantic Premium emoji entries from `game/premium_emoji.py`. Keep IDs allowlisted and provide Unicode fallbacks. Custom emoji are for bot output; do not store markup in channel JSON or render Telegram `tg-emoji` in the browser Mini App. Owner Telegram Premium enables the bot to send them in private, group, and supergroup chats.
- Keep credentials in `.env`; use `.env.example` as the template. Configure `MINIAPP_API_ENABLED`, `MINIAPP_BOT_USERNAME`, `MINIAPP_ALLOWED_ORIGINS`, and a public HTTPS API URL before enabling Mini App links.

## Key files

- `main.py` — bot startup and optional same-process API startup.
- `miniapp_api.py` — authenticated Mini App routes and Telegram `initData` validation.
- `channel_db.py`, `shadows_db.py` — Telegram channel-backed persistence.
- `game/economy.py` — shared claim/shop operations; `game/shop.py` — catalogue and purchase rules.
- `game/rich_text.py`, `game/rich_message.py`, `game/rich_send.py` — bot text format, document building, and transport.
- `game/premium_emoji.py` — custom emoji allowlist, semantic tokens, and Unicode fallbacks.
- `handlers/` — bot commands, including guild mutations and Mini App launch links (`game/miniapp.py`).
- `miniapp/src/` — app shell, screens, components, API client, and System HUD styles. See `miniapp/README.md` for setup/deployment and `docs/superpowers/specs/2026-09-28-miniapp-system-ui-design.md` for the UI spec.

## Local workflow (PowerShell)

Install Python dependencies from the repository root:

```powershell
python -m pip install -r requirements.txt
if (-not (Test-Path .env)) { Copy-Item .env.example .env }
python main.py
```

Run the static Mini App from `miniapp/`:

```powershell
cd miniapp
if (-not (Test-Path .env.local)) { Copy-Item .env.example .env.local }
npm ci
npm run dev
```

A regular browser checks layout and navigation; authenticated requests need Telegram `initData`. For the full flow, expose the frontend and bot API through HTTPS, set `VITE_API_BASE_URL` and the exact frontend origin in `MINIAPP_ALLOWED_ORIGINS`, then open the app from Telegram. See `miniapp/README.md`.

Run the frontend check from `miniapp/` and the Python check from the repository root:

```powershell
npm run build
python -m py_compile miniapp_api.py game/economy.py game/rich_text.py game/premium_emoji.py
```
