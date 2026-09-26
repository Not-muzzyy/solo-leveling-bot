# Hunter System Mini App

This is a TypeScript, React, and Vite frontend for the Telegram Mini App. It has no separate database: profile reads, claims, purchases, and guild directory reads go to the existing Python bot process, which uses its in-memory cache and persists records in the configured Telegram channels.

## What it supports

- Hunter profile and claim cooldown display, plus the existing daily Gold and XP claim.
- Shop catalogue browsing and item purchases, with the same item list and balance rules as the bot shop.
- Read-only guild standings, guild details, and member rosters.
- Telegram `initData` authentication. The frontend sends raw `Telegram.WebApp.initData`; the bot API validates its HMAC before deriving the Telegram user ID.

Guild creation, joining, leaving, and management remain bot commands. The Mini App does not expose those mutations.

## Local frontend

Install Node.js and npm, then run these commands from the repository root:

```powershell
cd miniapp
Copy-Item .env.example .env.local
npm install
npm run dev
```

Open the local Vite URL shown in the terminal to inspect the layout and navigation. A normal browser does not provide Telegram `initData`, so authenticated requests will show the Telegram-required state. Set `VITE_API_BASE_URL` in `.env.local` when you have a reachable API; an API URL alone does not replace Telegram authentication.

### Full Telegram flow on a local frontend

Telegram needs an HTTPS Mini App URL, and the Telegram WebView must be able to reach the API. Use HTTPS tunnels for the local Vite server on port `5173` and, if the bot API is local, for port `8080`. Set `VITE_API_BASE_URL` to the API's tunnel URL, then set the bot's `.env` values:

```dotenv
MINIAPP_API_ENABLED=true
MINIAPP_API_HOST=0.0.0.0
MINIAPP_API_PORT=8080
MINIAPP_BOT_USERNAME=your_bot_username
MINIAPP_ALLOWED_ORIGINS=https://your-frontend-tunnel.example
```

Start `python main.py` from the repository root. In `@BotFather`, temporarily set the bot's Main Mini App URL to the frontend tunnel URL. Then use `/claim`, `/shop`, or `/guild info` in Telegram; each command opens its matching app section. The API tunnel must use HTTPS too, and its URL must be the value of `VITE_API_BASE_URL`.

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

Claim and shop writes update Telegram-backed records through the shared bot service. Telegram stores hunter and inventory records as separate messages, so a process interruption between those writes cannot provide database-grade atomic transactions; the implementation serializes app/bot claim and shop requests and attempts compensating saves if a write fails.
