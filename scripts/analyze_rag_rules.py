#!/usr/bin/env python3
"""
Analyze RAG rules and extract key trading strategy constraints
"""
import json
import re
from collections import Counter
from pathlib import Path

# Load the exported RAG rules
project_root = Path(__file__).parent.parent
rules_file = project_root / "rag_rules_export.json"

with open(rules_file, 'r') as f:
    all_data = json.load(f)

documents = all_data.get('documents', [])

print("="*80)
print("📊 RAG STRATEGY RULES ANALYSIS")
print("="*80)
print(f"\nTotal documents: {len(documents)}\n")

# Extract all content
all_content = []
for doc in documents:
    content = doc.get('content', '')
    if content:
        all_content.append(content)

full_text = ' '.join(all_content).lower()

print("="*80)
print("🎯 KEY STRATEGY RULES EXTRACTION")
print("="*80)

# Define rule patterns to search for
rule_patterns = {
    'Liquidity Sweep': [
        r'liquidity.*?sweep',
        r'sweep.*?liquidity',
        r'take.*?out.*?liquidity',
        r'liquidity.*?grab'
    ],
    'Fresh Zone': [
        r'fresh.*?zone',
        r'untapped.*?zone',
        r'first.*?touch',
        r'avoid.*?retest',
        r'no.*?retest'
    ],
    'HTF Trend': [
        r'htf.*?trend',
        r'higher.*?timeframe.*?trend',
        r'trend.*?alignment',
        r'overall.*?trend'
    ],
    'Risk-Reward': [
        r'risk.*?reward.*?1:(\d+)',
        r'rr.*?ratio.*?1:(\d+)',
        r'target.*?1:(\d+)'
    ],
    'Entry Type': [
        r'break.*?of.*?candle',
        r'boc',
        r'directional.*?close',
        r'flip.*?entry',
        r'bullish.*?close',
        r'bearish.*?close'
    ],
    'Stop Loss': [
        r'stop.*?loss.*?below.*?zone',
        r'sl.*?below.*?wick',
        r'stop.*?below.*?demand',
        r'stop.*?above.*?supply'
    ],
    'Zone Quality': [
        r'strong.*?zone',
        r'clear.*?zone',
        r'valid.*?zone',
        r'quality.*?zone'
    ],
    'Market Structure': [
        r'market.*?structure',
        r'break.*?of.*?structure',
        r'bos',
        r'choch',
        r'change.*?of.*?character'
    ],
    'Time Filter': [
        r'session.*?time',
        r'trading.*?hours',
        r'optimal.*?time',
        r'7:00.*?a\.?m',
        r'3:00.*?p\.?m'
    ],
    'Touch Count': [
        r'first.*?touch',
        r'second.*?touch',
        r'multiple.*?touch',
        r'retrace',
        r'retest'
    ]
}

print("\n🔍 Rule Frequency Analysis:\n")

rule_findings = {}

for rule_name, patterns in rule_patterns.items():
    matches = 0
    examples = []

    for pattern in patterns:
        found = re.findall(pattern, full_text)
        matches += len(found)

        if found:
            # Get first few examples
            examples.extend(found[:3])

    rule_findings[rule_name] = {
        'count': matches,
        'examples': examples[:5]
    }

    if matches > 0:
        print(f"✅ {rule_name}: {matches} mentions")
        if examples:
            print(f"   Examples: {', '.join(str(e) for e in examples[:3])}")
    else:
        print(f"⚠️  {rule_name}: Not mentioned")

print("\n" + "="*80)
print("📋 EXTRACTED STRATEGY RULES SUMMARY")
print("="*80)

# Extract specific RR ratios mentioned
rr_ratios = re.findall(r'1:(\d+(?:\.\d+)?)', full_text)
if rr_ratios:
    rr_counter = Counter(rr_ratios)
    print("\n💰 Risk-Reward Ratios Found:")
    for ratio, count in rr_counter.most_common(5):
        print(f"   • 1:{ratio} — {count} mentions")

# Extract specific requirements
print("\n📌 MANDATORY REQUIREMENTS (Most Mentioned):")

mandatory_keywords = [
    ('liquidity sweep', 'Liquidity Sweep Required'),
    ('fresh zone', 'Fresh Zones Preferred'),
    ('untapped', 'Untapped Zones Required'),
    ('demand zone', 'Demand Zone Trading'),
    ('supply zone', 'Supply Zone Trading'),
    ('directional close', 'Directional Close Entry'),
    ('break of candle', 'Break of Candle Entry'),
    ('market structure', 'Market Structure Analysis'),
    ('stop loss', 'Stop Loss Placement'),
]

for keyword, description in mandatory_keywords:
    count = full_text.count(keyword)
    if count >= 10:
        print(f"   🔴 {description}: {count} mentions (CRITICAL)")
    elif count >= 5:
        print(f"   🟡 {description}: {count} mentions (Important)")
    elif count > 0:
        print(f"   🟢 {description}: {count} mentions (Optional)")

print("\n" + "="*80)
print("🎯 TOP 20 STRATEGY RULES (Most Specific)")
print("="*80)

# Find bullet points that look like rules (start with -)
rule_bullets = []
for doc in documents[:100]:  # Check first 100 docs
    content = doc.get('content', '')
    # Split by lines and find bullet points
    lines = content.split('\n')
    for line in lines:
        line = line.strip()
        if line.startswith('- ') and len(line) > 20:
            rule_bullets.append(line[2:])  # Remove "- " prefix

# Remove duplicates and sort by length (more specific = longer)
unique_rules = list(set(rule_bullets))
unique_rules.sort(key=len, reverse=True)

print()
for i, rule in enumerate(unique_rules[:20], 1):
    # Truncate long rules
    if len(rule) > 120:
        rule = rule[:120] + "..."
    print(f"{i:2}. {rule}")

print("\n" + "="*80)
print("✅ ANALYSIS COMPLETE")
print("="*80)

# Save summary
summary = {
    'total_documents': len(documents),
    'rule_frequency': {k: v['count'] for k, v in rule_findings.items()},
    'rr_ratios_found': dict(Counter(rr_ratios).most_common(10)),
    'top_rules': unique_rules[:50]
}

summary_file = project_root / "rag_rules_summary.json"
with open(summary_file, 'w') as f:
    json.dump(summary, f, indent=2)

print(f"\n📄 Summary saved to: {summary_file}")
print("\nNext: Review the rules above and compare with Pine Script filters\n")
