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


## React SPA preview

A framework-based UI foundation is now available at `frontend/spa.html` (React + React Router + Tailwind CDN).

- Login route: `/spa.html#/login` (router handles `/login` inside SPA)
- Protected routes: chat/settings/memory/models/admin
- Legacy pages remain available (`chat.html`, `admin.html`, etc.) during migration.
