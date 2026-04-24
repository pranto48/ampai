# AmpAI – Local Docker & Dyad Preview Setup

## 1️⃣ Local Docker (development)
- **Database**: Postgres + Redis containers defined in `docker-compose.yml`.
- **Environment**: Copy `.env.example` → `.env` and keep values as-is.
- **Run**: `docker compose up -d --build`

## 2️⃣ Dyad Preview (temporary public URL using Supabase)
- **Environment**: Copy `.env.dyad.example` → `.env.dyad` (or set variables in the Dyad UI).
  - `SUPABASE_URL` – your Supabase project URL
  - `SUPABASE_ANON_KEY` – the anon key from Supabase → Settings → API
  - `JWT_SECRET`, `ADMIN_USERNAME`, `ADMIN_PASSWORD`, etc.
- **Database**: The backend automatically chooses the correct source:
  1. If `DATABASE_URL` is defined → uses local Postgres (Docker).
  2. If `DATABASE_URL` is not defined → falls back to `SUPABASE_URL` (Supabase).
- **Deploy**: Push to your branch and create a Dyad preview; the same codebase is used.

## 3️⃣ Switching Between DBs
- **Docker**: Always uses the Postgres container (`DATABASE_URL` points to `postgresql://ampai:ampai@db:5432/ampai`).
- **Dyad**: Does **not** set `DATABASE_URL`; it sets `SUPABASE_URL`/`SUPABASE_ANON_KEY`.
  - The helper `getDatabaseUrl()` in `backend/config.ts` returns whichever URL is present, so no code changes are required.

## 4️⃣ Optional Supabase Migrations
If you add new tables or indexes, run:
```bash
npm run migrate:supabase
```
This executes `scripts/migrate-supabase.ts` which applies `.sql` files placed in `backend/migrations/`.

---

That’s all you need to keep a single codebase while Docker uses its own local DB and Dyad preview uses Supabase. Happy coding! 🚀