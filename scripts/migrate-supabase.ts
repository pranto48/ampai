import { createClient } from '@supabase/supabase-js';
import * as fs from 'fs';
import * as path from 'path';

const supabaseUrl = process.env.SUPABASE_URL!;
const supabaseKey = process.env.SUPABASE_ANON_KEY!;
const supabase = createClient(supabaseUrl, supabaseKey);

const migrationsDir = path.resolve(__dirname, '../migrations');

async function runMigrations() {
  const files = fs.readdirSync(migrationsDir).filter(f => f.endsWith('.sql'));
  for (const file of files) {
    const sql = fs.readFileSync(path.join(migrationsDir, file), 'utf8');
    const { error } = await supabase.rpc('exec', { query: sql });
    if (error) {
      console.error(`❌ Migration ${file} failed:`, error);
      process.exit(1);
    } else {
      console.log(`✅ Migration ${file} applied`);
    }
  }
}

runMigrations()
  .then(() => console.log('🎉 All migrations completed'))
  .catch(err => {
    console.error('💥 Migration script error:', err);
    process.exit(1);
  });