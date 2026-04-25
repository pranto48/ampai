# AmpAI – Local Docker, Dyad Preview (Supabase) & Vercel Deployment#

## 1️⃣ Local Docker (development on your machine)

- **Database**: Uses the Postgres + Redis containers defined in `docker-compose.yml`.
- **Environment**: Copy `.env.example` → `.env` (keep the defaults).
- **Run**: `docker compose up -d --build`

## 2️⃣ Dyad Preview (temporary public URL that talks to Supabase)

- **Environment**: Create a `.env.dyad` file (or set variables in the Dyad UI) with:
  ```
  SUPABASE_URL=https://<YOUR-PROJECT>.supabase.co
  SUPABASE_ANON_KEY=public-anon-key
  DATABASE_URL=postgresql://postgres:<PASSWORD>@<HOST>:5432/<DB_NAME>   # Supabase Postgres connection string
  JWT_SECRET=dyad-preview-jwt-secret
  ADMIN_USERNAME=admin
  ADMIN_PASSWORD=admin123
  USER_USERNAME=user
  USER_PASSWORD=user123
  ```
- **Database logic**: The backend (`backend/main.py`) now uses:
  ```python
  DATABASE_URL = os.getenv("DATABASE_URL") or os.getenv("SUPABASE_URL") or "postgresql://ampai:ampai@db:5432/ampai"
  ```
  So when `DATABASE_URL` is set (as in the Dyad preview) it uses that Postgres (Supabase).  
  If you leave `DATABASE_URL` empty, it falls back to `SUPABASE_URL` (which is not a Postgres URL) – **you must set DATABASE_URL to the Supabase Postgres connection string** for the preview to work.
- **Static Files**: The backend serves the frontend from the `frontend/` directory. In Dyad, ensure the `frontend/` folder is present at the same level as `backend/`.
- **Deploy**: Push your code to the branch linked to Dyad and create a preview. The same source runs, but the DB is Supabase.

## 3️⃣ Vercel Frontend Deployment (optional, for a public web UI)

1. Push the repo to GitHub.
2. In Vercel, **New Project → Import Git Repository**.
3. Vercel will automatically pick up `vercel.json` which:
   - Rewrites `/api/*` requests to your backend host (set `YOUR_BACKEND_URL` to the public URL of your containerized backend, e.g. a Railway/Render/Fly service).
   - Serves the static React build from `/frontend`.
4. In Vercel **Settings → Environment Variables**, add:
   - `SUPABASE_URL` (your Supabase project URL)
   - `SUPABASE_ANON_KEY` (the anon key)
   - Any other keys your backend needs (e.g., `JWT_SECRET`, `OPENAI_API_KEY` if you use LLMs).
5. Deploy. Vercel gives you a URL like `https://your-app.vercel.app`.

## 4️⃣ Adding a Custom Domain (optional)

- **Vercel**: In the Vercel project → **Settings → Domains**, add your domain (e.g., `chat.ampai.com`) and follow the DNS instructions.
- **Backend host** (Railway/Render/Fly): Likewise add a domain like `api.ampai.com` and point it to your backend service.
- Vercel and your hosting provider will automatically provision SSL certificates.

## 5️⃣ Switching Between DBs (summary)

| Environment | Where `DATABASE_URL` comes from | What DB is used |
|-------------|--------------------------------|-----------------|
| **Docker (local)** | Set explicitly in `.env` or docker-compose (defaults to `postgresql://ampai:ampai@db:5432/ampai`) | Local Postgres container |
| **Dyad preview** | Set to Supabase Postgres connection string (from Supabase) | Supabase Postgres |
| **Vercel + backend host** | Either set `DATABASE_URL` to the Supabase Postgres URL **or** leave it unset and rely on the fallback to `SUPABASE_URL` (if your backend uses the same logic) | Supabase Postgres |

No code changes are required to switch; just adjust the environment variables.

## 6️⃣ Troubleshooting Dyad Preview

If the Dyad preview isn't working:

1. **Check the Dyad build logs** for errors during `pip install` or `uvicorn` startup.
2. **Verify the frontend files are present**: In Dyad, the `frontend/` directory should contain `index.html`, `style.css`, `app.js`, etc.
3. **Ensure the backend starts**: The `Procfile` tells Dyad to run `uvicorn main:app`. Check that the port is correctly set (Dyad sets the `PORT` environment variable).
4. **Static files**: The backend serves `frontend/` as static files. If the path is wrong, you'll get a 404. The updated `main.py` tries two possible paths.
5. **Database connection**: Make sure `DATABASE_URL` is set to the Supabase Postgres connection string (not the anon key URL).

## 7️⃣ Optional Supabase Migrations

If you add new tables or indexes, place `.sql` files in `backend/migrations/` and run:

```bash
npm run migrate:supabase
```

(This runs `scripts/migrate-supabase.ts` which executes the migrations against your Supabase project.)

---

That’s all you need to keep a single codebase while Docker uses its own local DB, Dyad preview uses Supabase, and Vercel serves the frontend. Happy coding! 🚀