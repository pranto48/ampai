# AmpAI deployment plan (Docker local + Vercel web + Supabase DB)

This gives you one codebase with two runtime modes:

- **Docker (local/private):** Postgres + Redis in Docker (as now)
- **Web (public):** Frontend on **Vercel**, backend on a container host (Railway/Render/Fly), DB on **Supabase Postgres**

> Recommended: Use Vercel only for frontend hosting. Keep backend as a normal container service.
> Running this full backend as Vercel serverless is not ideal (LangChain, Redis, background jobs, scheduler).

---

## 1) Architecture (recommended)

- `frontend/*` -> deploy on **Vercel**
- `backend/*` -> deploy on **Railway/Render/Fly.io** (Dockerfile)
- Database for cloud -> **Supabase Postgres** (`DATABASE_URL`)
- Redis for cloud -> Upstash Redis or Redis Cloud (`REDIS_URL`)

This keeps **same code** for Docker and cloud; only env vars differ.

---

## 2) Local Docker (unchanged)

Use your current compose for local:

```bash
docker compose up -d --build
```

Local env:
- `DATABASE_URL=postgresql://ampai:ampai@db:5432/ampai`
- `REDIS_URL=redis://redis:6379/0`

---

## 3) Cloud backend (container)

Deploy this repo (or backend folder) to Railway/Render/Fly with Docker.

Set env vars on backend service:

- `DATABASE_URL` = Supabase pooling URL (Postgres)
- `REDIS_URL` = Upstash/Redis Cloud URL
- `JWT_SECRET` = long random secret
- `ADMIN_USERNAME`, `ADMIN_PASSWORD`
- optional model/API env vars (OpenRouter/OpenAI/etc)

Backend must expose HTTP (example: `https://api.yourdomain.com`).

---

## 4) Vercel frontend deploy

### Option A (quick): static + API rewrite

Use `vercel.json` in repo root (template included), set destination backend URL.

Then:

```bash
vercel
vercel --prod
```

### Option B: Dyad flow

If you manage frontend in Dyad:
1. Import repo in Dyad
2. Point project root to this repo
3. Publish connected project to Vercel
4. Ensure rewrite `/api/*` points to your backend URL

---

## 5) Domain setup

### Vercel (frontend domain)
- Add custom domain in Vercel project -> `app.yourdomain.com`
- Update DNS records as Vercel suggests (A/CNAME)

### Backend domain
- Add backend custom domain in Railway/Render/Fly -> `api.yourdomain.com`
- Update DNS CNAME/A record

---

## 6) Supabase database notes

- Create project in Supabase
- Copy **connection string** (prefer pooling URL)
- Put it in backend `DATABASE_URL`
- Run any startup migrations by app boot (or add explicit migration script if needed)

---

## 7) Keep Docker + Vercel in sync

Use branch flow:
1. Develop/test in Docker locally
2. Push same branch to git
3. Vercel auto-deploy frontend
4. Backend host auto-deploy container

This gives same code with different env/runtime.

---

## 8) Better long-term plan (recommended)

- Split frontend and backend folders into separate deploy pipelines
- Add Alembic migrations for schema safety
- Add health endpoint checks in Vercel rewrite target validation
- Add CI to run syntax checks + smoke tests before deploy
