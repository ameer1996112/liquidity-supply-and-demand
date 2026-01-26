"""
Test script to validate optimizer setup before running full optimization.
This script checks:
1. Environment variables are set
2. Supabase connection works
3. trading_signals table exists and has data
4. ai_features column has the expected structure
"""

import os
import sys
from supabase import create_client, Client
import json


def test_environment_variables():
    """Test if required environment variables are set."""
    print("1️⃣  Testing environment variables...")

    supabase_url = os.getenv('SUPABASE_URL')
    supabase_key = os.getenv('SUPABASE_KEY')

    if not supabase_url:
        print("   ❌ SUPABASE_URL is not set")
        print("   💡 Fix: export SUPABASE_URL='https://your-project.supabase.co'")
        return False

    if not supabase_key:
        print("   ❌ SUPABASE_KEY is not set")
        print("   💡 Fix: export SUPABASE_KEY='your-anon-key'")
        return False

    print(f"   ✓ SUPABASE_URL: {supabase_url[:30]}...")
    print(f"   ✓ SUPABASE_KEY: {supabase_key[:20]}...")
    return True, supabase_url, supabase_key


def test_supabase_connection(url, key):
    """Test if we can connect to Supabase."""
    print("\n2️⃣  Testing Supabase connection...")

    try:
        supabase: Client = create_client(url, key)
        print("   ✓ Successfully connected to Supabase")
        return True, supabase
    except Exception as e:
        print(f"   ❌ Connection failed: {e}")
        return False, None


def test_table_exists(supabase):
    """Test if trading_signals table exists and has data."""
    print("\n3️⃣  Testing trading_signals table...")

    try:
        # Try to fetch a single record
        response = supabase.table('trading_signals').select('*').limit(1).execute()

        if not response.data:
            print("   ⚠️  Table exists but has no data")
            print("   💡 Add some trading signals to the table first")
            return False

        print(f"   ✓ Table exists and contains data")
        return True, response.data[0]
    except Exception as e:
        print(f"   ❌ Error accessing table: {e}")
        print("   💡 Make sure the 'trading_signals' table exists in your database")
        return False, None


def test_required_columns(sample_record):
    """Test if required columns exist in the table."""
    print("\n4️⃣  Testing required columns...")

    required_columns = ['pnl_percent', 'exit_type', 'ai_features']
    missing_columns = []

    for col in required_columns:
        if col not in sample_record:
            missing_columns.append(col)
        else:
            print(f"   ✓ Column '{col}' exists")

    if missing_columns:
        print(f"   ❌ Missing columns: {', '.join(missing_columns)}")
        return False

    return True


def test_ai_features_structure(sample_record):
    """Test if ai_features has the expected structure."""
    print("\n5️⃣  Testing ai_features structure...")

    ai_features = sample_record.get('ai_features')

    if not ai_features:
        print("   ❌ ai_features is empty or null")
        return False

    # Parse if string
    if isinstance(ai_features, str):
        try:
            ai_features = json.loads(ai_features)
        except json.JSONDecodeError:
            print("   ❌ ai_features is not valid JSON")
            return False

    expected_features = ['rsi', 'adx', 'zone_freshness', 'liquidity_swept', 'zone_quality']
    found_features = []
    missing_features = []

    for feature in expected_features:
        if feature in ai_features:
            found_features.append(feature)
            value = ai_features[feature]
            print(f"   ✓ '{feature}': {value} ({type(value).__name__})")
        else:
            missing_features.append(feature)

    if missing_features:
        print(f"\n   ⚠️  Missing features: {', '.join(missing_features)}")
        print(f"   💡 The optimizer expects these features in ai_features:")
        for feature in expected_features:
            print(f"      - {feature}")
        return False

    return True


def test_data_quality(supabase):
    """Test data quality and provide statistics."""
    print("\n6️⃣  Analyzing data quality...")

    try:
        response = supabase.table('trading_signals').select('pnl_percent, exit_type, ai_features').execute()
        total_records = len(response.data)

        print(f"   ✓ Total records: {total_records}")

        # Count records with valid pnl_percent
        valid_pnl = sum(1 for r in response.data if r.get('pnl_percent') is not None)
        print(f"   ✓ Records with valid PnL: {valid_pnl} ({valid_pnl/total_records*100:.1f}%)")

        # Count by exit_type
        wins = sum(1 for r in response.data if r.get('exit_type') == 'Win')
        losses = sum(1 for r in response.data if r.get('exit_type') == 'Loss')
        print(f"   ✓ Wins: {wins}, Losses: {losses}")

        # Check ai_features completeness
        valid_features = 0
        for record in response.data:
            ai_features = record.get('ai_features')
            if ai_features:
                if isinstance(ai_features, str):
                    try:
                        ai_features = json.loads(ai_features)
                    except:
                        continue

                if all(key in ai_features for key in ['rsi', 'adx', 'zone_freshness', 'liquidity_swept', 'zone_quality']):
                    valid_features += 1

        print(f"   ✓ Records with complete AI features: {valid_features} ({valid_features/total_records*100:.1f}%)")

        if valid_features < 20:
            print(f"\n   ⚠️  Warning: Only {valid_features} records have complete features")
            print(f"   💡 For best results, you should have at least 50-100 complete records")
            return False

        return True

    except Exception as e:
        print(f"   ❌ Error analyzing data: {e}")
        return False


def main():
    """Run all validation tests."""
    print("="*60)
    print("🔍 Trading Filter Optimizer - Setup Validation")
    print("="*60)

    all_passed = True

    # Test 1: Environment variables
    result = test_environment_variables()
    if not result or result[0] is False:
        print("\n❌ Setup validation failed")
        sys.exit(1)

    _, supabase_url, supabase_key = result

    # Test 2: Supabase connection
    success, supabase = test_supabase_connection(supabase_url, supabase_key)
    if not success:
        all_passed = False
    else:
        # Test 3: Table exists
        result = test_table_exists(supabase)
        if not result or result[0] is False:
            all_passed = False
        else:
            _, sample_record = result

            # Test 4: Required columns
            if not test_required_columns(sample_record):
                all_passed = False

            # Test 5: AI features structure
            if not test_ai_features_structure(sample_record):
                all_passed = False

            # Test 6: Data quality
            if not test_data_quality(supabase):
                all_passed = False

    print("\n" + "="*60)
    if all_passed:
        print("✅ All tests passed! You're ready to run the optimizer.")
        print("\n📝 Next step:")
        print("   python optimize_filters.py")
    else:
        print("❌ Some tests failed. Please fix the issues above.")
        print("\n📖 See OPTIMIZER_GUIDE.md for detailed setup instructions")

    print("="*60)

    sys.exit(0 if all_passed else 1)


if __name__ == "__main__":
    main()
