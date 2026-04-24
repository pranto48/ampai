import { getDatabaseUrl } from './config';

// Example usage (replace existing direct process.env.DATABASE_URL calls):
const dbUrl = getDatabaseUrl();

// If you use a Postgres client:
// import { Pool } from 'pg';
// const pool = new Pool({ connectionString: dbUrl });

// If you use Supabase client elsewhere, you can import supabase from config:
// import { supabase } from './config';

export { getDatabaseUrl };