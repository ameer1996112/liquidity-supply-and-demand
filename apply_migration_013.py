#!/usr/bin/env python3
"""
Apply Migration 013: Account Enhancements

This script applies the migration to add provider, account_type, meta_api_account_id,
and other account enhancement columns to the account_strategies table.
"""

import os
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from supabase import create_client
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_ANON_KEY = os.getenv("SUPABASE_ANON_KEY")

if not SUPABASE_URL or not SUPABASE_ANON_KEY:
    print("❌ Error: SUPABASE_URL and SUPABASE_ANON_KEY must be set")
    sys.exit(1)

# Read migration file
migration_file = project_root / "migrations" / "013_account_enhancements.sql"
if not migration_file.exists():
    print(f"❌ Error: Migration file not found at {migration_file}")
    sys.exit(1)

with open(migration_file, "r") as f:
    migration_sql = f.read()

# Split into individual statements (skip comments and empty lines)
statements = []
current_statement = []
for line in migration_sql.split("\n"):
    # Skip comment-only lines
    if line.strip().startswith("--"):
        continue

    current_statement.append(line)

    # If line ends with semicolon, it's the end of a statement
    if line.strip().endswith(";"):
        statement = "\n".join(current_statement).strip()
        if statement and not statement.startswith("--"):
            statements.append(statement)
        current_statement = []

print(f"🔍 Found {len(statements)} SQL statements in migration 013")
print(f"📋 Migration file: {migration_file}")
print("\n" + "="*60)

# Create Supabase client
supabase = create_client(SUPABASE_URL, SUPABASE_ANON_KEY)

# Apply each statement
success_count = 0
error_count = 0

for i, statement in enumerate(statements, 1):
    # Show first 80 chars of statement
    preview = statement.replace("\n", " ")[:80] + "..."
    print(f"\n[{i}/{len(statements)}] {preview}")

    try:
        # Execute via RPC or direct SQL
        # Note: Supabase client doesn't support raw SQL directly
        # We'll need to use the PostgREST API or a custom RPC function

        # For ALTER TABLE and CREATE INDEX, we need direct database access
        # This script is meant to be run with proper database credentials
        print("⚠️  Skipping - This statement requires direct database access")
        print("    Please run this migration using Supabase Studio or psql")

    except Exception as e:
        print(f"❌ Error: {e}")
        error_count += 1

print("\n" + "="*60)
print("\n📌 IMPORTANT: This migration requires direct database access")
print("   Please apply it using one of these methods:")
print("\n   1. Supabase Studio (SQL Editor):")
print("      - Go to https://supabase.com/dashboard")
print("      - Navigate to SQL Editor")
print("      - Copy and paste the migration file")
print("      - Click 'Run'")
print("\n   2. Using psql with direct database connection:")
print(f"      psql <DATABASE_URL> -f {migration_file}")
print("\n   3. Railway (if deployed there):")
print("      - Go to your Railway project")
print("      - Open the Postgres service")
print("      - Use the Query tab to run the migration")
print("\n" + "="*60)
