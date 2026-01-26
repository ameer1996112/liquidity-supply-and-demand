"""
Apply Optimized Filters to New Trading Signals
===============================================
This script demonstrates how to use the optimized filter parameters
from optimized_filters.json to filter new trading signals in production.
"""

import json
from typing import Dict, Any


class OptimizedFilterApplicator:
    """Applies optimized filters to trading signals."""

    def __init__(self, filters_file: str = 'optimized_filters.json'):
        """
        Load optimized filter parameters from JSON file.

        Args:
            filters_file: Path to the optimized_filters.json file
        """
        with open(filters_file, 'r') as f:
            data = json.load(f)
            self.filters = data['best_params']

        print("✓ Loaded optimized filters:")
        for param, value in self.filters.items():
            print(f"  • {param}: {value}")
        print()

    def should_take_trade(self, signal: Dict[str, Any]) -> bool:
        """
        Determine if a trading signal passes the optimized filters.

        Args:
            signal: Dictionary containing signal data with ai_features

        Returns:
            True if signal passes all filters, False otherwise

        Example:
            signal = {
                'symbol': 'BTCUSD',
                'direction': 'LONG',
                'ai_features': {
                    'rsi': 58.5,
                    'adx': 32.0,
                    'zone_freshness': 7,
                    'liquidity_swept': True,
                    'zone_quality': 0.75
                }
            }

            applicator = OptimizedFilterApplicator()
            if applicator.should_take_trade(signal):
                print("✓ Take this trade!")
            else:
                print("✗ Skip this trade")
        """
        ai_features = signal.get('ai_features', {})

        # Extract features
        rsi = ai_features.get('rsi')
        adx = ai_features.get('adx')
        zone_freshness = ai_features.get('zone_freshness')
        liquidity_swept = ai_features.get('liquidity_swept', False)
        zone_quality = ai_features.get('zone_quality')

        # Check if any required features are missing
        if None in [rsi, adx, zone_freshness, zone_quality]:
            print("  ⚠️  Missing required AI features")
            return False

        # Apply filters
        filters_passed = []
        filters_failed = []

        # Zone Freshness
        if zone_freshness >= self.filters['min_freshness']:
            filters_passed.append(f"✓ Zone Freshness: {zone_freshness} >= {self.filters['min_freshness']}")
        else:
            filters_failed.append(f"✗ Zone Freshness: {zone_freshness} < {self.filters['min_freshness']}")

        # RSI
        if rsi <= self.filters['max_rsi']:
            filters_passed.append(f"✓ RSI: {rsi} <= {self.filters['max_rsi']}")
        else:
            filters_failed.append(f"✗ RSI: {rsi} > {self.filters['max_rsi']}")

        # ADX
        if adx >= self.filters['min_adx']:
            filters_passed.append(f"✓ ADX: {adx} >= {self.filters['min_adx']}")
        else:
            filters_failed.append(f"✗ ADX: {adx} < {self.filters['min_adx']}")

        # Zone Quality
        if zone_quality >= self.filters['min_zone_quality']:
            filters_passed.append(f"✓ Zone Quality: {zone_quality} >= {self.filters['min_zone_quality']}")
        else:
            filters_failed.append(f"✗ Zone Quality: {zone_quality} < {self.filters['min_zone_quality']}")

        # Liquidity Sweep
        if self.filters['require_liquidity_sweep']:
            if liquidity_swept:
                filters_passed.append(f"✓ Liquidity Swept: {liquidity_swept}")
            else:
                filters_failed.append(f"✗ Liquidity Swept: {liquidity_swept} (required: True)")
        else:
            filters_passed.append(f"✓ Liquidity Swept: Not required")

        # Return result
        return len(filters_failed) == 0

    def evaluate_signal(self, signal: Dict[str, Any], verbose: bool = True) -> Dict[str, Any]:
        """
        Evaluate a signal and return detailed results.

        Args:
            signal: Trading signal to evaluate
            verbose: Print detailed filter results

        Returns:
            Dictionary with evaluation results
        """
        passed = self.should_take_trade(signal)

        result = {
            'passed': passed,
            'signal': signal,
            'filters': self.filters
        }

        if verbose:
            print(f"\n{'='*60}")
            print(f"Signal Evaluation: {signal.get('symbol', 'N/A')} {signal.get('direction', 'N/A')}")
            print(f"{'='*60}")

            ai_features = signal.get('ai_features', {})

            # Display features
            print("\n📊 Signal Features:")
            print(f"  RSI:             {ai_features.get('rsi', 'N/A')}")
            print(f"  ADX:             {ai_features.get('adx', 'N/A')}")
            print(f"  Zone Freshness:  {ai_features.get('zone_freshness', 'N/A')}")
            print(f"  Liquidity Swept: {ai_features.get('liquidity_swept', 'N/A')}")
            print(f"  Zone Quality:    {ai_features.get('zone_quality', 'N/A')}")

            # Display filter results
            print("\n🎯 Filter Results:")

            ai_features = signal.get('ai_features', {})
            rsi = ai_features.get('rsi')
            adx = ai_features.get('adx')
            zone_freshness = ai_features.get('zone_freshness')
            liquidity_swept = ai_features.get('liquidity_swept', False)
            zone_quality = ai_features.get('zone_quality')

            # Check each filter
            checks = [
                (zone_freshness >= self.filters['min_freshness'],
                 f"Zone Freshness {zone_freshness} >= {self.filters['min_freshness']}"),
                (rsi <= self.filters['max_rsi'],
                 f"RSI {rsi} <= {self.filters['max_rsi']}"),
                (adx >= self.filters['min_adx'],
                 f"ADX {adx} >= {self.filters['min_adx']}"),
                (zone_quality >= self.filters['min_zone_quality'],
                 f"Zone Quality {zone_quality} >= {self.filters['min_zone_quality']}"),
                (not self.filters['require_liquidity_sweep'] or liquidity_swept,
                 f"Liquidity Swept: {liquidity_swept} (required: {self.filters['require_liquidity_sweep']})")
            ]

            for check_passed, check_desc in checks:
                if check_passed:
                    print(f"  ✓ {check_desc}")
                else:
                    print(f"  ✗ {check_desc}")

            # Final verdict
            print(f"\n{'='*60}")
            if passed:
                print("✅ VERDICT: TAKE THIS TRADE")
            else:
                print("❌ VERDICT: SKIP THIS TRADE")
            print(f"{'='*60}\n")

        return result


def example_usage():
    """Example usage of the OptimizedFilterApplicator."""

    print("="*60)
    print("🎯 Optimized Filter Applicator - Example Usage")
    print("="*60)
    print()

    # Initialize applicator
    try:
        applicator = OptimizedFilterApplicator()
    except FileNotFoundError:
        print("❌ Error: optimized_filters.json not found")
        print("   Please run optimize_filters.py first")
        return

    # Example signals
    test_signals = [
        {
            'symbol': 'BTCUSD',
            'direction': 'LONG',
            'price': 45000,
            'ai_features': {
                'rsi': 58.5,
                'adx': 32.0,
                'zone_freshness': 7,
                'liquidity_swept': True,
                'zone_quality': 0.75
            }
        },
        {
            'symbol': 'ETHUSD',
            'direction': 'SHORT',
            'price': 3200,
            'ai_features': {
                'rsi': 72.0,
                'adx': 18.5,
                'zone_freshness': 3,
                'liquidity_swept': False,
                'zone_quality': 0.45
            }
        },
        {
            'symbol': 'SOLUSD',
            'direction': 'LONG',
            'price': 120,
            'ai_features': {
                'rsi': 55.0,
                'adx': 35.0,
                'zone_freshness': 8,
                'liquidity_swept': True,
                'zone_quality': 0.85
            }
        }
    ]

    # Evaluate each signal
    results = []
    for signal in test_signals:
        result = applicator.evaluate_signal(signal, verbose=True)
        results.append(result)

    # Summary
    passed_count = sum(1 for r in results if r['passed'])
    total_count = len(results)

    print(f"\n{'='*60}")
    print(f"📊 Summary: {passed_count}/{total_count} signals passed filters")
    print(f"{'='*60}")


if __name__ == "__main__":
    example_usage()
