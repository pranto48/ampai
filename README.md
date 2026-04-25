# AmpAI

Single codebase deployment for:

- **Docker local development** (local Postgres + Redis)
- **Dyad preview** (Supabase Postgres)
- **Vercel frontend publish** (backend hosted separately)

## Quick start (Docker local)

```bash
cp .env.example .env
docker compose up -d --build
```

Open: `http://localhost:8001`

## Deployment guide

For Dyad + Vercel + domain setup, see:

- `DEPLOYMENT_VERCEL_SUPABASE.md`

## Environment templates

- `.env.example` → local Docker defaults
- `.env.dyad.example` → Dyad/Supabase template
