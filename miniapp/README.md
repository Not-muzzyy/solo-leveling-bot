# Hunter System Mini App

This is a TypeScript, React, and Vite static frontend for the Telegram Mini App. The Python bot process also serves the authenticated FastAPI API and shares its initialized `ChannelDB`; there is no separate Mini App database or game-data service. Hunter, inventory, and guild records remain JSON messages in the configured Telegram channels.

## Implementation status

Mini App Tasks 1–6 are present in repository history. Bot Premium emoji Task 7 is implemented in the local working tree; Task 8 verification remains pending.

## What it supports

- Hunter profile and claim cooldown display, plus the existing daily Gold and XP claim.
- Shop catalogue browsing and item purchases, with the same item list and balance rules as the bot shop.
- Read-only guild standings, guild details, and member rosters.
- Telegram `initData` authentication. The frontend sends raw `Telegram.WebApp.initData`; the bot API validates its HMAC before deriving the Telegram user ID.
- A Solo Leveling System HUD with Profile as the home screen, plus Claim, Shop, and Guilds navigation.

Guild creation, joining, leaving, and management remain bot commands. The Mini App does not expose those mutations.

Claim and shop requests share the locked operations in `game/economy.py` with the bot handlers. Telegram stores hunter and inventory in separate messages, so writes cannot be atomic; compensating writes reduce risk. A `storage_error` can indicate a partial or uncertain Telegram write. Before retrying, check the hunter's balance and inventory, then contact a bot admin. Purchase request deduplication is kept in process memory and does not survive a bot restart.

## Bot Premium emoji

Premium custom emoji are a bot-message feature, rendered through the shared `telegram-text` and rich-message helpers. The bot uses the curated registry in `game/premium_emoji.py` for user-facing sections and retains Unicode fallbacks. The bot owner's Telegram Premium enables these bot-sent emoji in private, group, and supergroup chats. The browser Mini App has its own CSS/UI and does not render Telegram `tg-emoji` markup; custom emoji markup is not stored in Telegram channel JSON records.

## Local frontend

Install Node.js and npm, then run these commands from the repository root:

```powershell
cd miniapp
if (-not (Test-Path .env.local)) { Copy-Item .env.example .env.local }
npm ci
npm run dev
```

Open the local Vite URL shown in the terminal to inspect layout and navigation. A normal browser does not provide Telegram `initData`, so authenticated requests will show the Telegram-required state. Set `VITE_API_BASE_URL` in `.env.local` when you have a reachable API; an API URL alone does not replace Telegram authentication. `npm run build` type-checks and builds the static bundle in `dist/`.

### Full Telegram flow on a local frontend

Telegram needs an HTTPS Mini App URL, and the Telegram WebView must be able to reach the API. Use HTTPS tunnels for the local Vite server on port `5173` and, if the bot API is local, for port `8080`. Set `VITE_API_BASE_URL` to the API's tunnel URL, then set the bot's `.env` values:

```dotenv
MINIAPP_API_ENABLED=true
MINIAPP_API_HOST=0.0.0.0
MINIAPP_API_PORT=8080
MINIAPP_BOT_USERNAME=your_bot_username
MINIAPP_ALLOWED_ORIGINS=https://your-frontend-tunnel.example
```

Start `python main.py` from the repository root. In `@BotFather`, temporarily set the bot's Main Mini App URL to the frontend tunnel URL. Then use `/claim`, `/shop`, or `/guild info` in Telegram; each command opens its matching app section. The API tunnel must use HTTPS too, and its URL must be the value of `VITE_API_BASE_URL`. Telegram authorization data is rejected after 24 hours (or if dated more than 30 seconds in the future); reopen the Mini App from Telegram to obtain fresh data.

To check the frontend bundle separately, run `npm run build` from `miniapp/`; Vite writes the static output to `miniapp/dist/`.

## Bot API setup

The API must run beside the bot so it shares the initialized `ChannelDB` cache and Telegram client. Configure the existing bot host:

```dotenv
MINIAPP_API_ENABLED=true
MINIAPP_API_HOST=0.0.0.0
MINIAPP_API_PORT=8080
MINIAPP_BOT_USERNAME=your_bot_username
MINIAPP_ALLOWED_ORIGINS=https://your-miniapp-domain.example
```

Use the host's assigned port when it provides one. Give the API a public HTTPS origin and set that exact origin in `MINIAPP_ALLOWED_ORIGINS`. Do not put `BOT_TOKEN` in the Mini App or its hosting provider's public frontend variables.

After deploying the frontend, configure the bot's **Main Mini App** URL in `@BotFather`. The `/claim`, `/shop`, and `/guild info` commands then link to that app with the matching `startapp` section. These command links stay on the bot-only implementation until both `MINIAPP_API_ENABLED` and `MINIAPP_BOT_USERNAME` are set.

## Deploy the frontend

Only the static Mini App belongs on Vercel or GitHub Pages. The API still belongs on the always-on bot host.

### Vercel

Create a Vercel project with `miniapp` as the Root Directory, framework **Vite**, build command `npm run build`, and output directory `dist`. Set `VITE_API_BASE_URL` to the bot API's public HTTPS origin, deploy, then add the final Vercel origin to `MINIAPP_ALLOWED_ORIGINS`.

### GitHub Pages

Build the `miniapp` directory with `VITE_API_BASE_URL` set to the bot API origin. For a repository project page, also set `VITE_BASE_PATH=/<repository-name>/`; use `/` for a user or organization site. Publish the generated `miniapp/dist` directory with GitHub Pages and allow its HTTPS origin in `MINIAPP_ALLOWED_ORIGINS`.

## API routes

| Route | Purpose |
| --- | --- |
| `GET /api/v1/me` | Hunter status, inventory count, and current guild |
| `POST /api/v1/claim` | Claim the daily reward |
| `GET /api/v1/shop/catalog` | Read shop catalogue |
| `POST /api/v1/shop/purchases` | Buy a catalogue item |
| `GET /api/v1/guilds?sort=power` | Read guild directory |
| `GET /api/v1/guilds/{guild_id}` | Read one guild and roster |

Claim and shop writes update Telegram-backed records through the shared bot service. Requests are serialized across app and bot handlers, with compensating saves when a write fails.
