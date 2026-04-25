# AmpAI deployment: same codebase for Docker (local DB) + Vercel (Supabase DB)

This setup gives you exactly what you asked for:

- **Local Docker** uses its **own local Postgres + Redis**.
- **Dyad preview** uses **Supabase Postgres** (and cloud Redis).
- **Vercel** publishes the **web view** from the same repo.
- You can attach a **custom domain** in Vercel.

---

## 1) Local Docker (local DB)

1. Copy local env values:

```bash
cp .env.example .env
```

2. Start services:

```bash
docker compose up -d --build
```

3. App endpoints (default ports):
- App: `http://localhost:8001`
- Postgres: `localhost:5433`
- Redis: `localhost:6380`

Docker service uses this local DB by default:
- `DATABASE_URL=postgresql://ampai:ampai@db:5432/ampai`

---

## 2) Dyad preview (Supabase DB)

1. Copy Dyad env template:

```bash
cp .env.dyad.example .env.dyad
```

2. Fill these values in Dyad environment variables:
- `DATABASE_URL` = Supabase Postgres **pooling** connection string
- `SUPABASE_URL` and `SUPABASE_ANON_KEY`
- `REDIS_URL` = Upstash / Redis Cloud URL
- `JWT_SECRET`, `ADMIN_USERNAME`, `ADMIN_PASSWORD`, `USER_USERNAME`, `USER_PASSWORD`

3. Publish Dyad preview from the same branch.

> Important: Dyad must use `DATABASE_URL` for Supabase Postgres. Do not use `SUPABASE_URL` as a DB connection string.

---

## 3) Publish web app on Vercel

1. Push this repo to GitHub.
2. In Vercel: **New Project → Import Git Repository**.
3. Keep repo root as project root (uses `vercel.json`).
4. Edit `vercel.json` and replace:
   - `https://YOUR_BACKEND_URL` with your backend public URL (Railway/Render/Fly).
5. Deploy:

```bash
vercel
vercel --prod
```

Your Vercel frontend will call backend APIs through `/api/*` rewrite.

---

## 4) Backend hosting for Vercel API target

Because this app is FastAPI + long-running features, host backend as a container service (Railway/Render/Fly), not Vercel serverless.

Set backend environment variables:
- `DATABASE_URL` = Supabase Postgres URL
- `REDIS_URL` = cloud Redis
- `JWT_SECRET`, admin/user credentials
- Any model provider keys you use

---

## 5) Add custom domain

### Frontend domain (Vercel)
1. Vercel project → **Settings → Domains**.
2. Add your domain (example: `app.yourdomain.com`).
3. Add DNS records exactly as Vercel shows.
4. Wait for SSL provisioning.

### Backend domain (hosting provider)
1. In Railway/Render/Fly service, add domain (example: `api.yourdomain.com`).
2. Add provider DNS records.
3. Update `vercel.json` rewrite destination to your backend domain.

---

## 6) One-codebase workflow

1. Make UI/backend code changes once in this repo.
2. Test locally with Docker.
3. Push to Git.
4. Dyad/Vercel deploy from same commit.

Result:
- Docker keeps local DB for local development.
- Cloud environments use Supabase DB.
