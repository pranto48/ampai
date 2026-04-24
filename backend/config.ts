export const getDatabaseUrl = () => {
  // 1️⃣ Prefer the explicit DATABASE_URL – this is set by Docker‑Compose locally.
  const direct = process.env.DATABASE_URL;
  if (direct) return direct;

  // 2️⃣ If DATABASE_URL is not set, fall back to the Supabase connection string.
  //    Supabase provides a PostgreSQL URL under Project Settings → Connection → PostgreSQL.
  const supabaseUrl = process.env.SUPABASE_URL;
  if (supabaseUrl) return supabaseUrl;

  // 3️⃣ If neither is defined we cannot continue – fail fast with a clear message.
  throw new Error('DATABASE_URL or SUPABASE_URL must be defined in the environment');
}