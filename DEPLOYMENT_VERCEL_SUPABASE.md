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

> Use `DATABASE_URL` for Postgres. `SUPABASE_URL` is not a Postgres DSN.

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


## 7) Docker troubleshooting

If `docker compose up --build` fails with:

- `failed to solve: invalid containerPort: 8000#`

then your `Dockerfile` is malformed (the `EXPOSE 8000` line got merged with a comment).
Use the Dockerfile in this repo where these are separate lines:

- `EXPOSE 8000`
- `CMD ["uvicorn", "backend.main:app", ...]`

Also, this repo does not require a compose profile for normal startup, so use:

```bash
docker compose up --build -d
```

