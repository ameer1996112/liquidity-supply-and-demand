#!/usr/bin/env python3
"""
Diagnose AI Filtering Issues
Check why AI models are approving all trades instead of filtering
"""

import os
import sys
from pathlib import Path

# Add project root to path
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from config import get_settings
from supabase import create_client

def main():
    print("=" * 80)
    print("AI FILTERING DIAGNOSTIC REPORT")
    print("=" * 80)

    s = get_settings()

    # === CONFIGURATION ANALYSIS ===
    print("\n📋 CURRENT AI CONFIGURATION:")
    print(f"  AI_FILTER_ENABLED: {s.ai_filter_enabled}")
    print(f"  AI_PROVIDER: {s.ai_provider}")
    print(f"  AI_MIN_CONFIDENCE: {s.ai_min_confidence}")
    print(f"  AI_QUICK_MODEL: {getattr(s, 'ai_quick_model', 'NOT SET')}")
    print(f"  AI_DEEP_MODEL: {getattr(s, 'ai_deep_model', 'NOT SET')}")

    print(f"\n  ENABLE_LLM_FILTER: {getattr(s, 'enable_llm_filter', 'NOT SET')}")
    ai_mode = getattr(s, 'ai_mode', 'NOT SET')
    print(f"  AI_MODE: {ai_mode}")

    print(f"\n  ML_GUARDIAN_ENABLED: {s.ml_guardian_enabled}")
    print(f"  ML_MIN_CONFIDENCE: {s.ml_min_confidence} ({s.ml_min_confidence * 100}%)")

    # Check for shadow/warning modes
    ai_shadow = getattr(s, 'ai_shadow_mode', False)
    ml_warning_only = getattr(s, 'ml_warning_only_mode', False)
    print(f"\n  AI_SHADOW_MODE: {ai_shadow}")
    print(f"  ML_WARNING_ONLY_MODE: {ml_warning_only}")

    # === ISSUE DETECTION ===
    print("\n" + "=" * 80)
    print("⚠️  DETECTED ISSUES:")
    print("=" * 80)

    issues = []

    # Issue 1: AI Filter disabled
    if not s.ai_filter_enabled:
        issues.append({
            "severity": "CRITICAL",
            "issue": "AI_FILTER_ENABLED=false",
            "impact": "Ensemble Brain (RF + RAG + LLM) is completely bypassed",
            "fix": "Set AI_FILTER_ENABLED=true in Railway"
        })

    # Issue 2: AI mode is shadow
    if ai_mode == "shadow":
        issues.append({
            "severity": "CRITICAL",
            "issue": "AI_MODE=shadow",
            "impact": "AI runs but NEVER blocks trades (log-only mode)",
            "fix": "Set AI_MODE=enforce in Railway (or remove variable to default to 'shadow')"
        })

    # Issue 3: LLM filter disabled
    enable_llm = getattr(s, 'enable_llm_filter', True)
    if not enable_llm:
        issues.append({
            "severity": "HIGH",
            "issue": "ENABLE_LLM_FILTER=false",
            "impact": "LLM context layer bypassed, only RF model runs",
            "fix": "Set ENABLE_LLM_FILTER=true in Railway"
        })

    # Issue 4: ML confidence too low
    if s.ml_min_confidence < 0.60:
        issues.append({
            "severity": "MEDIUM",
            "issue": f"ML_MIN_CONFIDENCE={s.ml_min_confidence} (below 60%)",
            "impact": "RF model accepts low-quality trades (50% = coin flip)",
            "fix": "Set ML_MIN_CONFIDENCE=0.65 or higher in Railway"
        })

    # Issue 5: ML warning-only mode
    if ml_warning_only:
        issues.append({
            "severity": "MEDIUM",
            "issue": "ML_WARNING_ONLY_MODE=true",
            "impact": "RF confidence 10-60% shows WARNING but still allows trade",
            "fix": "Set ML_WARNING_ONLY_MODE=false in Railway"
        })

    # Issue 6: AI shadow mode
    if ai_shadow:
        issues.append({
            "severity": "HIGH",
            "issue": "AI_SHADOW_MODE=true",
            "impact": "AI decisions logged but never block trades",
            "fix": "Set AI_SHADOW_MODE=false in Railway"
        })

    if not issues:
        print("\n✅ No configuration issues detected!")
    else:
        for i, issue in enumerate(issues, 1):
            print(f"\n{i}. [{issue['severity']}] {issue['issue']}")
            print(f"   Impact: {issue['impact']}")
            print(f"   Fix: {issue['fix']}")

    # === RECENT TRADE ANALYSIS ===
    print("\n" + "=" * 80)
    print("📊 RECENT TRADE ANALYSIS (Last 7 days):")
    print("=" * 80)

    try:
        supabase = create_client(s.supabase_url, s.supabase_service_role_key or s.supabase_key)

        # Get recent signals
        result = supabase.table("trading_signals")\
            .select("signal_id,symbol,side,decision,rejection_reason,ai_confidence,ml_probability,ai_would_have_blocked,created_at")\
            .gte("created_at", "NOW() - interval '7 days'")\
            .order("created_at", desc=True)\
            .limit(20)\
            .execute()

        signals = result.data

        if not signals:
            print("\n⚠️  No signals found in last 7 days")
        else:
            approved = [s for s in signals if s.get("decision") == "approved"]
            rejected = [s for s in signals if s.get("decision") == "rejected"]

            print(f"\nTotal signals: {len(signals)}")
            print(f"  ✅ Approved: {len(approved)} ({len(approved)/len(signals)*100:.1f}%)")
            print(f"  ❌ Rejected: {len(rejected)} ({len(rejected)/len(signals)*100:.1f}%)")

            # Check for shadow mode evidence
            shadow_blocks = [s for s in signals if s.get("ai_would_have_blocked")]
            if shadow_blocks:
                print(f"\n⚠️  {len(shadow_blocks)} signals were approved despite AI wanting to block (shadow mode)")

            # Show recent signals
            print("\nRecent 10 signals:")
            print(f"{'Time':<20} {'Symbol':<10} {'Side':<5} {'Decision':<10} {'ML Prob':<10} {'Reason':<40}")
            print("-" * 100)

            for sig in signals[:10]:
                time = sig.get("created_at", "")[:19] if sig.get("created_at") else ""
                symbol = sig.get("symbol", "")
                side = sig.get("side", "")
                decision = sig.get("decision", "")
                ml_prob = sig.get("ml_probability")
                ml_str = f"{ml_prob:.1%}" if ml_prob is not None else "N/A"
                reason = (sig.get("rejection_reason") or "")[:40]

                print(f"{time:<20} {symbol:<10} {side:<5} {decision:<10} {ml_str:<10} {reason:<40}")

            # Analyze rejection reasons
            if rejected:
                print("\nRejection reasons breakdown:")
                reasons = {}
                for sig in rejected:
                    reason = sig.get("rejection_reason") or "Unknown"
                    # Extract first part of reason
                    key = reason.split(".")[0][:50]
                    reasons[key] = reasons.get(key, 0) + 1

                for reason, count in sorted(reasons.items(), key=lambda x: -x[1]):
                    print(f"  • {count:2d}× {reason}")

    except Exception as e:
        print(f"\n❌ Error querying database: {e}")

    # === RECOMMENDATIONS ===
    print("\n" + "=" * 80)
    print("💡 RECOMMENDATIONS:")
    print("=" * 80)

    if not s.ai_filter_enabled or ai_mode == "shadow":
        print("\n🔴 CRITICAL: Your AI is in SHADOW MODE - it's not actually filtering trades!")
        print("   This means ALL trades are passing through regardless of AI analysis.")
        print("\n   To enable strict filtering:")
        print("   1. railway variables --set AI_FILTER_ENABLED=true")
        print("   2. railway variables --set AI_MODE=enforce")
        print("   3. railway variables --set ENABLE_LLM_FILTER=true")
        print("   4. railway up  # Redeploy")

    if s.ml_min_confidence < 0.65:
        print("\n🟡 MEDIUM: RF threshold is too permissive")
        print(f"   Current: {s.ml_min_confidence} ({s.ml_min_confidence*100}%)")
        print("   Recommended for prop firm: 0.65-0.70 (65-70%)")
        print("   Fix: railway variables --set ML_MIN_CONFIDENCE=0.65")

    print("\n" + "=" * 80)
    print("📖 UNDERSTANDING AI MODES:")
    print("=" * 80)
    print("""
AI_MODE options:
  • shadow   = AI runs and logs decisions but NEVER blocks (safe for testing)
  • enforce  = AI blocks trades that fail filters (strict mode for live)

AI_FILTER_ENABLED options:
  • false = Ensemble Brain completely bypassed (no RF, RAG, or LLM)
  • true  = Full AI stack runs (RF → RAG → LLM chain)

ENABLE_LLM_FILTER options:
  • false = Only RF model runs (fast but no context awareness)
  • true  = Full ensemble (RF + RAG + LLM wisdom)

ML_MIN_CONFIDENCE (RF threshold):
  • 0.50 = Random coin flip (NOT RECOMMENDED)
  • 0.60 = Moderate edge (balanced, default)
  • 0.65 = Strong edge (conservative, good for prop firms)
  • 0.70+ = Very strong edge (ultra-conservative, few trades)
""")

if __name__ == "__main__":
    main()
