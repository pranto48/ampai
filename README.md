# AmpAI – Local Docker, Dyad Preview (Supabase) & Vercel Deployment

## Overview

This guide explains how to maintain a **single codebase** that works for:

- **Local development** via Docker (uses local Postgres + Redis)
- **Dyad Preview** (temporary public URL, uses Supabase Postgres)
- **Vercel-hosted frontend** (optional, for a public web UI)

The key idea: **Docker and Vercel share the same source code**, but each uses its own database configuration via environment variables.

---

## 1️⃣ Local Docker (development on your machine)

### How it works
- The `docker-compose.yml` spins up:
  - Postgres (with pgvector)
  - Redis
  - Your Python backend (FastAPI)
- The backend serves the frontend static files from the `frontend/` directory.
- Environment variables in `.env` point to the local Postgres container.

### Steps

1. Copy `.env.example` → `.env` (keep the defaults).
2. Build and start:
   ```bash
   docker compose up -d --build
   ```
3. Access the app at `http://localhost:8000`.

### Environment (`.env`)
```
DATABASE_URL=postgresql://ampai:ampai@db:5432/ampai
REDIS_URL=redis://redis:6379/0
JWT_SECRET=local-jwt-secret
ADMIN_USERNAME=admin
ADMIN_PASSWORD=admin123
USER_USERNAME=user
USER_PASSWORD=user123
```

---

## 2️⃣ Dyad Preview (temporary public URL using Supabase)

### How it works
- You push the same code to a Git branch linked to Dyad.
- Dyad builds and runs the backend, but **environment variables** tell it to use Supabase instead of local Postgres.
- The backend serves the frontend from the `frontend/` directory (mounted as static files).
- The catch-all route (`/{path:path}`) serves `index.html` for SPA routing.

### Steps

1. Create a `.env.dyad` file (or set variables in the Dyad UI) with:
   ```
   SUPABASE_URL=https://<YOUR-PROJECT>.supabase.co
   SUPABASE_ANON_KEY=public-anon-key
   DATABASE_URL=postgresql://postgres:<PASSWORD>@db.<PROJECT>.supabase.co:5432/postgres
   JWT_SECRET=dyad-preview-jwt-secret
   ADMIN_USERNAME=admin
   ADMIN_PASSWORD=admin123
   USER_USERNAME=user
   USER_PASSWORD=user123
   ```
   - **Important**: `DATABASE_URL` must be the **Supabase Postgres connection string** (Settings → Database → Connection string).

2. Ensure the `frontend/` folder is present at the same level as `backend/` in your repo.

3. Push to the branch linked to Dyad and create a preview.

4. Access the preview URL provided by Dyad.

### Backend behavior
- If `DATABASE_URL` is set → uses that Postgres (Supabase).
- If `DATABASE_URL` is empty → falls back to `SUPABASE_URL` (not a valid Postgres URL; will fail).
- Static files are served from `frontend/`.
- Catch-all route serves `index.html` for client-side routing.

---

## 3️⃣ Vercel Frontend Deployment (optional, for a public web UI)

If you want a separate public-facing frontend (e.g., `chat.yourdomain.com`):

### Steps

1. Push the repo to GitHub.
2. In Vercel, **New Project → Import Git Repository**.
3. Vercel automatically uses `vercel.json` to:
   - Rewrite `/api/*` requests to your backend host.
   - Serve the static React build from `/frontend`.
4. In Vercel **Settings → Environment Variables**, add:
   - `SUPABASE_URL`
   - `SUPABASE_ANON_KEY`
   - Any other keys your backend needs (`JWT_SECRET`, etc.)
5. Deploy. Vercel gives you a URL like `https://your-app.vercel.app`.

### Custom Domain (optional)
- In Vercel **Settings → Domains**, add your domain (e.g., `chat.yourdomain.com`) and follow DNS instructions.
- Your backend host (e.g., Railway/Render/Fly) should also have its own domain if needed.

---

## 4️⃣ Backend Host (optional, for API-only deployment)

If you deploy the backend separately (e.g., Railway, Render, Fly):

- Set environment variables:
  - `DATABASE_URL` = Supabase Postgres connection string
  - `SUPABASE_URL` = Supabase URL
  - `SUPABASE_ANON_KEY` = anon key
- Ensure the backend serves static files (the `STATIC_DIR` logic in `main.py` handles this).
- Update `vercel.json`'s rewrite destination to point to this backend host.

---

## 5️⃣ Switching Between DBs (summary)

| Environment | `DATABASE_URL` source | DB used |
|-------------|----------------------|---------|
| **Docker (local)** | `.env` (defaults to local Postgres) | Local Postgres container |
| **Dyad preview** | Set to Supabase Postgres connection string | Supabase Postgres |
| **Vercel + backend host** | Set to Supabase Postgres URL | Supabase Postgres |

No code changes are required—just adjust environment variables.

---

## 6️⃣ File Structure (important for static serving)

```
.
├── backend/
│   ├── main.py              # FastAPI app with static mount
│   ├── config.py            # getDatabaseUrl()
│   └── ...
├── frontend/
│   ├── index.html           # SPA entry
│   ├── style.css
│   ├── app.js
│   └── ...
├── docker-compose.yml
├── Dockerfile
├── vercel.json
├── .env.example
├── .env.dyad.example
└── README.md
```

---

## 7️⃣ Troubleshooting

### Dyad preview not working?

1. **Check build logs** for errors during `pip install` or `uvicorn` startup.
2. **Verify frontend files** exist in the Dyad build output:
   - `frontend/index.html`, `style.css`, `app.js` should be present.
3. **Ensure backend starts**:
   - The `Procfile` (if used) should run: `cd backend && uvicorn main:app --host 0.0.0.0 --port ${PORT:-8000}`
4. **Static files**:
   - The backend serves `frontend/` as static files. If the path is wrong, you'll get 404s.
   - The updated `main.py` tries multiple paths and logs what it finds.
5. **Database connection**:
   - Make sure `DATABASE_URL` is set to the Supabase Postgres connection string (not the anon key URL).

### Local Docker issues?
- Rebuild: `docker compose build`
- Check logs: `docker compose logs`
- Ensure ports are mapped correctly (e.g., `8000:8000`)

---

## 8️⃣ Optional: Supabase Migrations

If you add new tables or indexes:

```bash
npm run migrate:supabase
```

This runs `scripts/migrate-supabase.ts` which applies `.sql` files from `backend/migrations/`.

---

## 9️⃣ Summary

- **Single codebase** for Docker, Dyad preview, and Vercel.
- **Database switching** via environment variables (`DATABASE_URL`).
- **Static files** served from `frontend/` by the backend.
- **SPA routing** handled by a catch-all route.
- **No Docker reinstall needed** when updating the frontend—just push changes and redeploy Dyad or Vercel.

Happy coding! 🚀