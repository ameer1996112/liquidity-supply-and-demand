/**
 * Environment Variable Verification Script
 * Run during build or at runtime to diagnose missing Supabase credentials.
 *
 * Usage:
 *   node scripts/check_env.js
 *
 * Or add to package.json:
 *   "scripts": { "check-env": "node scripts/check_env.js" }
 */

console.log('\n========================================');
console.log('  ENVIRONMENT VARIABLE CHECK');
console.log('========================================\n');

const requiredVars = [
  'NEXT_PUBLIC_SUPABASE_URL',
  'NEXT_PUBLIC_SUPABASE_ANON_KEY',
];

const optionalVars = [
  'NEXT_PUBLIC_API_URL', // Backend API base (e.g. http://localhost:8000 or http://backend:8000)
];

let allPresent = true;

requiredVars.forEach((varName) => {
  const value = process.env[varName];
  const isPresent = !!value && value.length > 0;

  if (isPresent) {
    // Mask the value for security (show first 10 chars + ...)
    const masked =
      value.length > 15 ? value.substring(0, 10) + '...[HIDDEN]' : '[SET]';
    console.log(`  ✅ ${varName}: ${masked}`);
  } else {
    console.log(`  ❌ ${varName}: NOT SET`);
    allPresent = false;
  }
});

optionalVars.forEach((varName) => {
  const value = process.env[varName];
  const isPresent = !!value && value.length > 0;
  if (isPresent) {
    const masked = value.length > 30 ? value.substring(0, 25) + '...' : value;
    console.log(`  ℹ️  ${varName}: ${masked}`);
  } else {
    console.log(`  ⚪ ${varName}: not set (optional)`);
  }
});

console.log('\n----------------------------------------');

if (allPresent) {
  console.log('  ✅ All required environment variables are set!');
  console.log('  Supabase client should initialize correctly.\n');
  process.exit(0);
} else {
  console.log('  ❌ MISSING ENVIRONMENT VARIABLES');
  console.log('');
  console.log('  In Railway (Frontend Service), set these variables:');
  console.log('');
  console.log('    NEXT_PUBLIC_SUPABASE_URL=https://your-project.supabase.co');
  console.log('    NEXT_PUBLIC_SUPABASE_ANON_KEY=eyJhbGci...');
  console.log('');
  console.log(
    '  Note: The NEXT_PUBLIC_ prefix is REQUIRED for client-side access.\n'
  );
  process.exit(1);
}
