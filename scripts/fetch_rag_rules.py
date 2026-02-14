#!/usr/bin/env python3
"""
Fetch RAG strategy rules from Supabase document database
"""
import os
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from dotenv import load_dotenv
from supabase import create_client, Client
import json

# Load environment variables
load_dotenv()

# Supabase connection
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY")  # Use service role for full access

if not SUPABASE_URL or not SUPABASE_KEY:
    print("❌ Error: SUPABASE_URL or SUPABASE_SERVICE_ROLE_KEY not found in .env")
    sys.exit(1)

print(f"🔗 Connecting to Supabase: {SUPABASE_URL}")

try:
    # Initialize Supabase client
    supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
    print("✅ Connected to Supabase successfully\n")
except Exception as e:
    print(f"❌ Failed to connect to Supabase: {e}")
    sys.exit(1)

print("="*80)
print("🔍 SEARCHING FOR RAG STRATEGY RULES")
print("="*80)

# List of possible table names for RAG/strategy rules
possible_tables = [
    "documents",
    "strategy_rules",
    "rag_rules",
    "trading_rules",
    "strategy_documents",
    "embeddings",
    "knowledge_base",
    "rag_embeddings",
    "strategy_embeddings"
]

found_tables = []

print("\n📊 Scanning for relevant tables...\n")

for table_name in possible_tables:
    try:
        response = supabase.table(table_name).select("*").limit(1).execute()
        if response.data:
            found_tables.append(table_name)
            print(f"✅ Found table: {table_name}")

            # Get column names
            if response.data:
                columns = list(response.data[0].keys())
                print(f"   Columns: {', '.join(columns)}")

                # Check row count
                count_response = supabase.table(table_name).select("*", count="exact").execute()
                row_count = count_response.count if hasattr(count_response, 'count') else len(count_response.data)
                print(f"   Rows: {row_count}\n")
    except Exception as e:
        continue  # Table doesn't exist, skip silently

if not found_tables:
    print("❌ No relevant tables found!")
    print("\n💡 Available tables in your Supabase database:")
    print("   Please check your Supabase dashboard manually.")
    sys.exit(1)

print("="*80)
print(f"\n📋 RETRIEVING DATA FROM FOUND TABLES\n")
print("="*80)

all_rules = {}

for table_name in found_tables:
    print(f"\n🔍 Querying table: {table_name}")
    print("-"*80)

    try:
        # Fetch all data from the table
        response = supabase.table(table_name).select("*").execute()

        if response.data:
            all_rules[table_name] = response.data
            print(f"✅ Retrieved {len(response.data)} documents\n")

            # Show first 3 documents
            for i, doc in enumerate(response.data[:3]):
                print(f"\n--- Document {i+1} ---")

                # Pretty print with truncation for long content
                for key, value in doc.items():
                    if isinstance(value, str) and len(value) > 200:
                        print(f"  {key}: {value[:200]}... [truncated]")
                    else:
                        print(f"  {key}: {value}")

            if len(response.data) > 3:
                print(f"\n... and {len(response.data) - 3} more documents")
        else:
            print(f"⚠️  Table {table_name} is empty")

    except Exception as e:
        print(f"❌ Error querying {table_name}: {e}")

# Save all rules to a JSON file
output_file = project_root / "rag_rules_export.json"
with open(output_file, 'w') as f:
    json.dump(all_rules, f, indent=2, default=str)

print("\n" + "="*80)
print(f"✅ EXPORT COMPLETE")
print("="*80)
print(f"\n📄 All rules saved to: {output_file}")
print(f"📊 Total tables retrieved: {len(all_rules)}")
for table_name, data in all_rules.items():
    print(f"   • {table_name}: {len(data)} documents")

print("\n" + "="*80)
print("🎯 STRATEGY RULE ANALYSIS")
print("="*80)

# Try to extract strategy-specific rules
strategy_keywords = [
    'liquidity', 'sweep', 'zone', 'entry', 'exit', 'stop', 'target',
    'trend', 'filter', 'supply', 'demand', 'fresh', 'touch', 'HTF',
    'AI', 'score', 'grade', 'risk', 'RR', 'ratio'
]

print("\n🔎 Searching for strategy-related content...\n")

for table_name, documents in all_rules.items():
    print(f"\n📋 Table: {table_name}")
    print("-"*80)

    strategy_docs = []
    for doc in documents:
        # Convert doc to string and search for keywords
        doc_str = json.dumps(doc, default=str).lower()

        # Count keyword matches
        matches = sum(1 for keyword in strategy_keywords if keyword in doc_str)

        if matches >= 3:  # Document has at least 3 strategy keywords
            strategy_docs.append((doc, matches))

    if strategy_docs:
        # Sort by number of matches
        strategy_docs.sort(key=lambda x: x[1], reverse=True)

        print(f"✅ Found {len(strategy_docs)} strategy-related documents\n")

        for i, (doc, match_count) in enumerate(strategy_docs[:5]):  # Show top 5
            print(f"\n--- Strategy Document {i+1} (Matches: {match_count}) ---")
            for key, value in doc.items():
                if isinstance(value, str) and len(value) > 300:
                    print(f"  {key}: {value[:300]}...")
                else:
                    print(f"  {key}: {value}")
    else:
        print("⚠️  No strategy-specific documents found in this table")

print("\n" + "="*80)
print("✅ ANALYSIS COMPLETE")
print("="*80)
print(f"\nNext: Review the exported file and strategy documents above")
print(f"File: {output_file}\n")
