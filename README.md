# AmpAI

Single codebase for:

- **Docker local development** (local Postgres + Redis)
- **Dyad preview** (Supabase Postgres + cloud Redis)
- **Vercel web publish** (frontend + `/api/*` rewrite to backend)

## Quick start (local)

```bash
cp .env.example .env
docker compose up -d --build
```

Open: `http://localhost:8001` (or `http://<your-server-ip>:8001` from another device on your LAN)

## Deployment + domains

Follow the full guide:

- `DEPLOYMENT_VERCEL_SUPABASE.md`

## Environment templates

- `.env.example` (local Docker)
- `.env.dyad.example` (Dyad + Supabase)
- `.env.vercel.example` (Vercel template)

## Security

- Do not commit real API keys or DB passwords.
- Use publishable keys in browsers; keep secret/service-role keys server-only.


If you hit Docker build errors, check `DEPLOYMENT_VERCEL_SUPABASE.md` section **Docker troubleshooting**.


If the page is blank or backend exits with `SyntaxError`, pull latest code and rebuild containers (see Docker troubleshooting in `DEPLOYMENT_VERCEL_SUPABASE.md`).


Quick check if browser shows blank page:

```bash
docker compose ps
docker compose logs -f agent-web-app
```


If browser shows **"Unsafe attempt to load URL ... chrome-error://chromewebdata"**, the app endpoint is unreachable. Verify container health and logs, then refresh:

```bash
docker compose ps
docker compose logs --tail=200 agent-web-app
```


Container health check endpoint: `GET /healthz` (public).


## React UI

Home page (`/index.html`) now runs React + React Router + Tailwind (HashRouter) as the primary UI.

Legacy page URLs (`chat.html`, `settings.html`, `memory-explorer.html`, `ai-models.html`, `admin.html`, `login.html`) now redirect to React hash routes.

## SPA migration next steps

1. Move chat composer + message list from `chat.html` into React route `/chat`.
2. Move model/provider form into React route `/models`.
3. Move memory explorer table into React route `/memory`.
4. Move admin dashboard cards into React route `/admin` and keep role guard.
5. Replace Babel-CDN setup with Vite build when ready for production SPA bundle.
