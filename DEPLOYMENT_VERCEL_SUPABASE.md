# AmpAI deployment: Docker local + Dyad preview + Vercel publish + custom domain

This repository supports one codebase across environments:

- **Docker local** → local Postgres + local Redis
- **Dyad preview** → Supabase Postgres + cloud Redis
- **Vercel** → frontend publish with `/api/*` rewrite to your backend domain

---

## 0) Security first (important)

- Use **Supabase publishable key** in browser/frontend contexts.
- Never commit **secret/service-role** keys into git.
- Keep server-only secrets in provider dashboards (Dyad, Railway/Render/Fly, Vercel env vars).
- If a secret key was ever pasted/shared, rotate it in Supabase immediately.

---

## 1) Local Docker (local DB)

```bash
cp .env.example .env
docker compose up -d --build
```

Default local endpoints:
- App: `http://localhost:8001`
- Postgres: `localhost:5433`
- Redis: `localhost:6380`

Docker app uses local DB by default via compose:
- `DATABASE_URL=postgresql://ampai:ampai@db:5432/ampai`

---

## 2) Dyad preview (Supabase DB)

```bash
cp .env.dyad.example .env.dyad
```

Set these in Dyad project environment variables:
- `DATABASE_URL` (Supabase Postgres pooling URL)
- `SUPABASE_URL`
- `SUPABASE_ANON_KEY` (or keep compatibility while migrating to publishable key usage)
- `REDIS_URL` (Upstash/Redis Cloud)
- `JWT_SECRET`, `ADMIN_USERNAME`, `ADMIN_PASSWORD`, `USER_USERNAME`, `USER_PASSWORD`

> Use `DATABASE_URL` for Postgres. `SUPABASE_URL` is not a Postgres DSN.

Set these in Dyad project environment variables:
- `DATABASE_URL` (Supabase Postgres pooling URL)
- `SUPABASE_URL`
- `SUPABASE_ANON_KEY` (or keep compatibility while migrating to publishable key usage)
- `REDIS_URL` (Upstash/Redis Cloud)
- `JWT_SECRET`, `ADMIN_USERNAME`, `ADMIN_PASSWORD`, `USER_USERNAME`, `USER_PASSWORD`

## 3) Publish frontend on Vercel

1. Import this repo in Vercel.
2. Keep root as project root so `vercel.json` is used.
3. Replace `https://YOUR_BACKEND_URL` in `vercel.json` with your backend API URL.
4. Deploy:

```bash
vercel
vercel --prod
```

Optional local template for Vercel env values:

```bash
cp .env.vercel.example .env.vercel.local
```

---

## 4) Backend hosting for API

Host FastAPI backend as a container (Railway/Render/Fly preferred).

Set backend env vars:
- `DATABASE_URL` = Supabase Postgres URL
- `REDIS_URL` = cloud Redis URL
- `JWT_SECRET`, admin/user credentials
- model/provider keys as needed

---

## 5) Add custom domains

### Vercel (frontend)
1. Project → **Settings → Domains**
2. Add domain like `app.yourdomain.com`
3. Apply DNS records shown by Vercel
4. Wait for SSL issuance

### Backend host
1. Add domain like `api.yourdomain.com`
2. Apply DNS records from host provider
3. Update `vercel.json` rewrite destination to this backend domain

---

## 6) Day-to-day workflow

1. Build and test locally in Docker.
2. Push same commit/branch.
3. Dyad and Vercel deploy from same source.

Outcome:
- Local Docker keeps local DB.
- Cloud uses Supabase DB.

---

---

## 7) Docker troubleshooting

### A) Backend crash with `SyntaxError` in `/app/backend/main.py`

If logs show errors like:

- `SyntaxError: invalid syntax`
- broken import line such as `import refrom datetime ...`

then your checked-out `backend/main.py` is corrupted.
Use the latest repo version (this branch restores a valid `main.py`) and rebuild:

Also ensure the container starts with `uvicorn main:app` from `/app/backend`.
Using `uvicorn backend.main:app` can break imports like `from auth import ...` in this codebase.

```bash
git pull
docker compose down
docker compose up --build -d
```

### B) Build failure `invalid containerPort: 8000#`

This means the Dockerfile had a malformed line where `EXPOSE 8000` merged with text.
Use the fixed Dockerfile from this repo and rebuild.

### C) Redis warnings in logs

- `vm.overcommit_memory = 1` warning is host-kernel tuning advice and usually non-fatal for local dev.
- Redis "no authentication" warning is addressed by this compose setup using `--requirepass` and a passworded `REDIS_URL`.

You can set the password in `.env`:

```bash
REDIS_PASSWORD=your-strong-local-password
```


### D) Browser shows `chrome-error://chromewebdata` and page is blank

That browser message usually means the app URL is not reachable (container crashed or not listening), not a frontend code error.
Check:

```bash
docker compose ps
docker compose logs -f agent-web-app
```

If logs show import failures, rebuild with the fixed Dockerfile/compose in this repo.
