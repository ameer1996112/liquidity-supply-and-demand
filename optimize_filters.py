"""
Trading Signal Filter Optimization using Optuna
================================================
This script finds the optimal combination of indicator filters to maximize Net Profit
from historical trading signals stored in Supabase.

KEY FEATURES:
-------------
1. Flexible Filter Selection: Optuna decides which filters to enable/disable
2. Dynamic Parameter Tuning: Finds optimal thresholds for each indicator
3. Statistical Significance: Ensures minimum trade count for robust results
4. Comprehensive Metrics: Win rate, PnL, profit factor, and more
5. Before/After Comparison: Clear visualization of improvements

USAGE:
------
1. Set environment variables:
   export SUPABASE_URL='https://your-project.supabase.co'
   export SUPABASE_KEY='your-anon-key'

2. Run optimization:
   python optimize_filters.py

3. Results are saved to:
   - optimized_filters.json (machine-readable)
   - Console output (human-readable)

OPTIMIZATION STRATEGY:
---------------------
The algorithm tests different combinations of:
- RSI threshold (20-90)
- ADX threshold (10-50)
- Zone Freshness (1-10)
- Zone Quality (0.1-1.0)
- Liquidity Sweep requirement (True/False)
- Minimum trades for statistical significance (20-100)

It maximizes a weighted objective:
- 70% Total PnL
- 30% Average PnL per trade * trade count

This prevents overfitting to either high volume or cherry-picked trades.
"""

import os
import pandas as pd
import numpy as np
import optuna
from supabase import create_client, Client
from typing import Dict, Any
import json

# Try to load .env file if it exists
try:
    from dotenv import load_dotenv
    load_dotenv()  # Load from .env file in current directory
    load_dotenv('tests/.env')  # Also try tests/.env
except ImportError:
    pass  # dotenv not installed, use system environment variables


class TradingFilterOptimizer:
    """Optimizes trading signal filters using Optuna to maximize PnL."""

    def __init__(self, supabase_url: str, supabase_key: str):
        """
        Initialize the optimizer with Supabase credentials.

        Args:
            supabase_url: Your Supabase project URL
            supabase_key: Your Supabase API key
        """
        self.supabase: Client = create_client(supabase_url, supabase_key)
        self.df: pd.DataFrame = None
        self.original_stats: Dict[str, Any] = {}

    def load_data(self) -> pd.DataFrame:
        """
        Load all trading signals from Supabase and extract AI features.

        Returns:
            DataFrame with extracted features and outcomes
        """
        print("📊 Loading data from Supabase...")

        # Fetch all records from trading_signals table
        response = self.supabase.table('trading_signals').select('*').execute()

        if not response.data:
            raise ValueError("No data found in trading_signals table")

        # Convert to DataFrame
        self.df = pd.DataFrame(response.data)

        print(f"✓ Loaded {len(self.df)} trading signals")

        # Extract AI features from JSONB column
        self._extract_features()

        # Calculate original statistics
        self._calculate_original_stats()

        return self.df

    def _extract_features(self):
        """Extract individual features from the ai_features JSONB column."""
        print("🔍 Extracting AI features...")
        print(f"📋 Available columns: {list(self.df.columns)}")

        # Check if ai_features column exists
        if 'ai_features' in self.df.columns:
            # Parse JSONB column and extract each feature
            for idx, row in self.df.iterrows():
                ai_features = row['ai_features']

                # Handle both string and dict formats
                if isinstance(ai_features, str):
                    ai_features = json.loads(ai_features)
                elif ai_features is None:
                    ai_features = {}

                # Extract each feature
                self.df.at[idx, 'rsi'] = ai_features.get('rsi', np.nan)
                self.df.at[idx, 'adx'] = ai_features.get('adx', np.nan)
                self.df.at[idx, 'zone_freshness'] = ai_features.get('zone_freshness', np.nan)
                self.df.at[idx, 'liquidity_swept'] = ai_features.get('liquidity_swept', False)
                self.df.at[idx, 'zone_quality'] = ai_features.get('zone_quality', np.nan)

            # Convert to appropriate types
            self.df['rsi'] = pd.to_numeric(self.df['rsi'], errors='coerce')
            self.df['adx'] = pd.to_numeric(self.df['adx'], errors='coerce')
            self.df['zone_freshness'] = pd.to_numeric(self.df['zone_freshness'], errors='coerce')
            self.df['liquidity_swept'] = self.df['liquidity_swept'].astype(bool)
            self.df['zone_quality'] = pd.to_numeric(self.df['zone_quality'], errors='coerce')

            print(f"✓ Extracted features: RSI, ADX, Zone Freshness, Liquidity Swept, Zone Quality")
        else:
            print("⚠️  'ai_features' column not found. Checking for individual feature columns...")

            # Map alternative column names to expected names
            column_mapping = {
                'freshness': 'zone_freshness',
                'liq_swept': 'liquidity_swept',
                'base_quality': 'zone_quality',
                'pnl': 'pnl_percent',  # Use 'pnl' as pnl_percent
                'pnl_r': 'pnl_r'  # Also available: R-multiple PnL
            }

            # Apply column mappings
            for old_col, new_col in column_mapping.items():
                if old_col in self.df.columns:
                    if new_col not in self.df.columns:
                        self.df[new_col] = self.df[old_col]
                        print(f"✓ Mapped column: '{old_col}' → '{new_col}'")

            # Check if features are now available
            feature_cols = ['rsi', 'adx', 'zone_freshness', 'liquidity_swept', 'zone_quality', 'pnl_percent']
            missing_cols = [col for col in feature_cols if col not in self.df.columns]

            if missing_cols:
                print(f"❌ Still missing feature columns: {missing_cols}")
                print(f"\n⚠️  WARNING: The following features are missing from your data:")
                for col in missing_cols:
                    print(f"   - {col}")
                    # Create dummy columns filled with NaN/False
                    if col == 'liquidity_swept':
                        self.df[col] = False
                    else:
                        self.df[col] = np.nan
                print(f"\n✓ Created placeholder columns for missing features (filled with NaN/False)")
                print(f"  Optimization will continue, but filters for these features won't be effective.")
            else:
                print(f"✓ All required feature columns are available!")

        print(f"✓ Total valid records with PnL data: {len(self.df.dropna(subset=['pnl_percent']))}")

    def _calculate_original_stats(self):
        """Calculate statistics for the unfiltered dataset."""
        valid_trades = self.df.dropna(subset=['pnl_percent'])

        total_trades = len(valid_trades)
        winning_trades = len(valid_trades[valid_trades['exit_type'] == 'Win'])
        losing_trades = len(valid_trades[valid_trades['exit_type'] == 'Loss'])

        win_rate = (winning_trades / total_trades * 100) if total_trades > 0 else 0
        total_pnl = valid_trades['pnl_percent'].sum()
        avg_win = valid_trades[valid_trades['exit_type'] == 'Win']['pnl_percent'].mean() if winning_trades > 0 else 0
        avg_loss = valid_trades[valid_trades['exit_type'] == 'Loss']['pnl_percent'].mean() if losing_trades > 0 else 0

        avg_pnl = valid_trades['pnl_percent'].mean() if total_trades > 0 else 0

        self.original_stats = {
            'total_trades': total_trades,
            'winning_trades': winning_trades,
            'losing_trades': losing_trades,
            'win_rate': win_rate,
            'total_pnl': total_pnl,
            'avg_pnl': avg_pnl,
            'avg_win': avg_win,
            'avg_loss': avg_loss
        }

        print("\n" + "="*80)
        print("📈 BASELINE PERFORMANCE (No Filters Applied)")
        print("="*80)
        print(f"Total Trades:      {total_trades}")
        print(f"Winning Trades:    {winning_trades} ({win_rate:.2f}%)")
        print(f"Losing Trades:     {losing_trades} ({100-win_rate:.2f}%)")
        print(f"Win Rate:          {win_rate:.2f}%")
        print(f"Total PnL:         {total_pnl:.2f}%")
        print(f"Avg PnL/Trade:     {avg_pnl:.2f}%")
        print(f"Avg Win:           {avg_win:.2f}%")
        print(f"Avg Loss:          {avg_loss:.2f}%")

        # Calculate baseline profit factor
        total_wins_amount = avg_win * winning_trades
        total_losses_amount = abs(avg_loss * losing_trades)
        profit_factor = total_wins_amount / total_losses_amount if total_losses_amount != 0 else float('inf')
        print(f"Profit Factor:     {profit_factor:.2f}")
        print("="*80 + "\n")

    def objective(self, trial: optuna.Trial) -> float:
        """
        Optuna objective function to maximize Total PnL.

        This function allows Optuna to decide which filters to enable/disable
        for maximum flexibility in finding the golden combination.

        Args:
            trial: Optuna trial object

        Returns:
            Total PnL for the filtered trades
        """
        # Start with all valid trades
        filtered_df = self.df.dropna(subset=['pnl_percent']).copy()

        # RSI Filter - Let Optuna decide whether to use it
        use_rsi = trial.suggest_categorical('use_rsi_filter', [True, False])
        if use_rsi:
            max_rsi = trial.suggest_int('max_rsi', 20, 90, step=5)
            filtered_df = filtered_df[filtered_df['rsi'] <= max_rsi]

        # ADX Filter - Let Optuna decide whether to use it
        use_adx = trial.suggest_categorical('use_adx_filter', [True, False])
        if use_adx:
            min_adx = trial.suggest_int('min_adx', 10, 50, step=5)
            filtered_df = filtered_df[filtered_df['adx'] >= min_adx]

        # Zone Freshness Filter - Let Optuna decide whether to use it
        use_freshness = trial.suggest_categorical('use_freshness_filter', [True, False])
        if use_freshness:
            min_freshness = trial.suggest_int('min_freshness', 1, 10)
            filtered_df = filtered_df[filtered_df['zone_freshness'] >= min_freshness]

        # Zone Quality Filter - Let Optuna decide whether to use it
        use_quality = trial.suggest_categorical('use_quality_filter', [True, False])
        if use_quality:
            min_zone_quality = trial.suggest_float('min_zone_quality', 0.1, 1.0, step=0.1)
            filtered_df = filtered_df[filtered_df['zone_quality'] >= min_zone_quality]

        # Liquidity Sweep Filter - Let Optuna decide whether to use it
        use_liquidity = trial.suggest_categorical('use_liquidity_filter', [True, False])
        if use_liquidity:
            require_liquidity_sweep = trial.suggest_categorical('require_liquidity_sweep', [True, False])
            if require_liquidity_sweep:
                filtered_df = filtered_df[filtered_df['liquidity_swept'] == True]
            else:
                filtered_df = filtered_df[filtered_df['liquidity_swept'] == False]

        # Minimum trades for statistical significance
        min_trades = trial.suggest_int('min_trades_threshold', 20, 100, step=10)

        # If no trades pass the filter, return a very negative value
        if len(filtered_df) < min_trades:
            return -999999.0

        # Calculate total PnL
        total_pnl = filtered_df['pnl_percent'].sum()

        # Optional: Calculate average PnL per trade for better optimization
        # This prevents overfitting to just high volume
        avg_pnl_per_trade = total_pnl / len(filtered_df)

        # Weighted objective: Favor both high total PnL and good per-trade performance
        # 70% weight on total PnL, 30% weight on consistency (avg PnL * trade count)
        objective_value = (0.7 * total_pnl) + (0.3 * avg_pnl_per_trade * len(filtered_df))

        return objective_value

    def optimize(self, n_trials: int = 200) -> Dict[str, Any]:
        """
        Run Optuna optimization to find the best filter parameters.

        Args:
            n_trials: Number of optimization trials to run

        Returns:
            Dictionary containing the best parameters and results
        """
        print(f"🚀 Starting optimization with {n_trials} trials...")
        print("⏳ This may take a few moments...\n")

        # Create Optuna study (maximize Total PnL)
        study = optuna.create_study(
            direction='maximize',
            study_name='trading_filter_optimization',
            sampler=optuna.samplers.TPESampler(seed=42)
        )

        # Run optimization
        study.optimize(self.objective, n_trials=n_trials, show_progress_bar=True)

        # Get best parameters
        best_params = study.best_params
        best_value = study.best_value

        print("\n" + "="*80)
        print("🏆 OPTIMIZATION COMPLETE - GOLDEN COMBINATION FOUND!")
        print("="*80)
        print(f"Best Objective Value: {best_value:.2f}")

        print("\n🎯 ACTIVE FILTERS (Best Parameters):")
        print("-" * 80)

        # Group parameters by filter type for better readability
        filter_groups = {
            'RSI': ['use_rsi_filter', 'max_rsi'],
            'ADX': ['use_adx_filter', 'min_adx'],
            'Zone Freshness': ['use_freshness_filter', 'min_freshness'],
            'Zone Quality': ['use_quality_filter', 'min_zone_quality'],
            'Liquidity Sweep': ['use_liquidity_filter', 'require_liquidity_sweep'],
            'Other': ['min_trades_threshold']
        }

        for filter_name, param_keys in filter_groups.items():
            relevant_params = {k: v for k, v in best_params.items() if k in param_keys}
            if relevant_params:
                print(f"\n  {filter_name}:")
                for param, value in relevant_params.items():
                    if param.startswith('use_') and not value:
                        print(f"    ❌ {param:35s} = {value} (Filter DISABLED)")
                    elif param.startswith('use_') and value:
                        print(f"    ✅ {param:35s} = {value} (Filter ENABLED)")
                    else:
                        print(f"       {param:35s} = {value}")

        print("\n" + "="*80)

        # Calculate optimized statistics
        optimized_stats = self._calculate_optimized_stats(best_params)

        # Display comparison
        self._display_comparison(optimized_stats)

        return {
            'best_params': best_params,
            'best_value': best_value,
            'original_stats': self.original_stats,
            'optimized_stats': optimized_stats,
            'study': study
        }

    def _calculate_optimized_stats(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Calculate statistics using the optimized parameters."""
        # Apply the best filters conditionally
        filtered_df = self.df.dropna(subset=['pnl_percent']).copy()

        # Apply RSI filter if enabled
        if params.get('use_rsi_filter', False):
            max_rsi = params.get('max_rsi')
            filtered_df = filtered_df[filtered_df['rsi'] <= max_rsi]

        # Apply ADX filter if enabled
        if params.get('use_adx_filter', False):
            min_adx = params.get('min_adx')
            filtered_df = filtered_df[filtered_df['adx'] >= min_adx]

        # Apply Zone Freshness filter if enabled
        if params.get('use_freshness_filter', False):
            min_freshness = params.get('min_freshness')
            filtered_df = filtered_df[filtered_df['zone_freshness'] >= min_freshness]

        # Apply Zone Quality filter if enabled
        if params.get('use_quality_filter', False):
            min_zone_quality = params.get('min_zone_quality')
            filtered_df = filtered_df[filtered_df['zone_quality'] >= min_zone_quality]

        # Apply Liquidity Sweep filter if enabled
        if params.get('use_liquidity_filter', False):
            require_liquidity_sweep = params.get('require_liquidity_sweep')
            if require_liquidity_sweep:
                filtered_df = filtered_df[filtered_df['liquidity_swept'] == True]
            else:
                filtered_df = filtered_df[filtered_df['liquidity_swept'] == False]

        total_trades = len(filtered_df)
        winning_trades = len(filtered_df[filtered_df['exit_type'] == 'Win'])
        losing_trades = len(filtered_df[filtered_df['exit_type'] == 'Loss'])

        win_rate = (winning_trades / total_trades * 100) if total_trades > 0 else 0
        total_pnl = filtered_df['pnl_percent'].sum()
        avg_pnl = filtered_df['pnl_percent'].mean() if total_trades > 0 else 0
        avg_win = filtered_df[filtered_df['exit_type'] == 'Win']['pnl_percent'].mean() if winning_trades > 0 else 0
        avg_loss = filtered_df[filtered_df['exit_type'] == 'Loss']['pnl_percent'].mean() if losing_trades > 0 else 0

        # Calculate profit factor
        total_wins = avg_win * winning_trades if winning_trades > 0 else 0
        total_losses = abs(avg_loss * losing_trades) if losing_trades > 0 else 0
        profit_factor = total_wins / total_losses if total_losses != 0 else float('inf')

        return {
            'total_trades': total_trades,
            'winning_trades': winning_trades,
            'losing_trades': losing_trades,
            'win_rate': win_rate,
            'total_pnl': total_pnl,
            'avg_pnl': avg_pnl,
            'avg_win': avg_win,
            'avg_loss': avg_loss,
            'profit_factor': profit_factor
        }

    def _display_comparison(self, optimized_stats: Dict[str, Any]):
        """Display before/after comparison with enhanced metrics."""
        print("\n📊 PERFORMANCE COMPARISON: ORIGINAL vs OPTIMIZED")
        print("="*80)
        print(f"{'Metric':<25} {'Original':>15} {'Optimized':>15} {'Change':>15} {'% Change':>10}")
        print("-"*80)

        metrics = [
            ('Total Trades', 'total_trades', '', False),
            ('Winning Trades', 'winning_trades', '', False),
            ('Losing Trades', 'losing_trades', '', False),
            ('Win Rate', 'win_rate', '%', True),
            ('Total PnL', 'total_pnl', '%', True),
            ('Avg PnL/Trade', 'avg_pnl', '%', True),
            ('Avg Win', 'avg_win', '%', True),
            ('Avg Loss', 'avg_loss', '%', True),
        ]

        for metric_name, metric_key, suffix, show_pct_change in metrics:
            original = self.original_stats.get(metric_key, 0)
            optimized = optimized_stats.get(metric_key, 0)

            if metric_key in ['total_trades', 'winning_trades', 'losing_trades']:
                change = optimized - original
                pct_change = ((optimized / original - 1) * 100) if original != 0 else 0
                print(f"{metric_name:<25} {original:>15.0f} {optimized:>15.0f} "
                      f"{change:>+15.0f} {pct_change:>9.1f}%")
            else:
                change = optimized - original
                pct_change = ((optimized / original - 1) * 100) if original != 0 else 0
                print(f"{metric_name:<25} {original:>14.2f}{suffix} {optimized:>14.2f}{suffix} "
                      f"{change:>+14.2f}{suffix} {pct_change:>9.1f}%")

        # Add profit factor
        orig_pf = self._calculate_profit_factor(self.original_stats)
        opt_pf = optimized_stats.get('profit_factor', 0)
        pf_change = opt_pf - orig_pf
        print(f"{'Profit Factor':<25} {orig_pf:>15.2f} {opt_pf:>15.2f} "
              f"{pf_change:>+15.2f} {((opt_pf/orig_pf-1)*100 if orig_pf != 0 else 0):>9.1f}%")

        print("="*80)

        # Key improvements summary
        win_rate_improvement = optimized_stats['win_rate'] - self.original_stats['win_rate']
        pnl_improvement = optimized_stats['total_pnl'] - self.original_stats['total_pnl']
        trades_kept = optimized_stats['total_trades'] / self.original_stats['total_trades'] * 100

        print("\n✨ KEY IMPROVEMENTS SUMMARY")
        print("="*80)
        print(f"Win Rate Improvement:     {self.original_stats['win_rate']:.2f}% → {optimized_stats['win_rate']:.2f}% "
              f"({win_rate_improvement:+.2f} percentage points)")
        print(f"Total PnL Improvement:    {self.original_stats['total_pnl']:.2f}% → {optimized_stats['total_pnl']:.2f}% "
              f"({pnl_improvement:+.2f}%)")
        print(f"Profit Factor:            {orig_pf:.2f} → {opt_pf:.2f} "
              f"({(opt_pf/orig_pf if orig_pf != 0 else 0):.2f}x improvement)")
        print(f"Trade Selectivity:        Using {optimized_stats['total_trades']} of {self.original_stats['total_trades']} trades "
              f"({trades_kept:.1f}%)")
        print(f"Filtered Out:             {self.original_stats['total_trades'] - optimized_stats['total_trades']} trades "
              f"({100-trades_kept:.1f}%)")

        # Calculate expected value
        expected_value = optimized_stats['avg_pnl']
        print(f"\n💰 Expected Value per Trade: {expected_value:.2f}%")
        print(f"   (Average profit/loss per trade with optimal filters)")

        print("="*80 + "\n")

    def _calculate_profit_factor(self, stats: Dict[str, Any]) -> float:
        """Calculate profit factor from stats."""
        total_wins = stats.get('avg_win', 0) * stats.get('winning_trades', 0)
        total_losses = abs(stats.get('avg_loss', 0) * stats.get('losing_trades', 0))
        return total_wins / total_losses if total_losses != 0 else float('inf')


def main():
    """Main execution function."""
    # Load credentials from environment variables
    SUPABASE_URL = os.getenv('SUPABASE_URL')
    # Check for both SUPABASE_KEY and SUPABASE_ANON_KEY (common variants)
    SUPABASE_KEY = os.getenv('SUPABASE_KEY') or os.getenv('SUPABASE_ANON_KEY')

    if not SUPABASE_URL or not SUPABASE_KEY:
        raise ValueError(
            "Please set SUPABASE_URL and SUPABASE_KEY (or SUPABASE_ANON_KEY) environment variables.\n"
            "Example:\n"
            "  export SUPABASE_URL='https://your-project.supabase.co'\n"
            "  export SUPABASE_KEY='your-anon-key'\n\n"
            "Or create a .env file with:\n"
            "  SUPABASE_URL=https://your-project.supabase.co\n"
            "  SUPABASE_ANON_KEY=your-anon-key"
        )

    # Initialize optimizer
    optimizer = TradingFilterOptimizer(SUPABASE_URL, SUPABASE_KEY)

    # Load data
    optimizer.load_data()

    # Run optimization
    results = optimizer.optimize(n_trials=200)

    # Optionally, save results to a file
    print("💾 Saving results to optimized_filters.json...")

    import json
    with open('optimized_filters.json', 'w') as f:
        json.dump({
            'best_params': results['best_params'],
            'best_value': float(results['best_value']),
            'original_stats': {k: float(v) if isinstance(v, (int, float)) else v
                              for k, v in results['original_stats'].items()},
            'optimized_stats': {k: float(v) if isinstance(v, (int, float)) else v
                               for k, v in results['optimized_stats'].items()}
        }, f, indent=2)

    print("✓ Results saved to optimized_filters.json")

    # Save Python code for easy integration
    print("\n💾 Generating Python code for easy integration...")
    _generate_filter_code(results['best_params'])

    print("\n🎉 Optimization complete! Use these filters in your trading strategy.")
    print("📝 Check 'apply_optimal_filters.py' for ready-to-use filter function.")


def _generate_filter_code(params: Dict[str, Any]):
    """Generate Python code to apply the optimal filters."""
    code = '''"""
Auto-generated optimal filter function
Generated by optimize_filters.py
"""

def apply_optimal_filters(df):
    """
    Apply the optimal filters found by Optuna optimization.

    Args:
        df: DataFrame with trading signals and extracted AI features

    Returns:
        Filtered DataFrame containing only high-quality signals
    """
    import pandas as pd

    filtered_df = df.copy()

'''

    # Add filter conditions based on enabled filters
    if params.get('use_rsi_filter', False):
        code += f"    # RSI Filter\n"
        code += f"    filtered_df = filtered_df[filtered_df['rsi'] <= {params['max_rsi']}]\n\n"

    if params.get('use_adx_filter', False):
        code += f"    # ADX Filter (trend strength)\n"
        code += f"    filtered_df = filtered_df[filtered_df['adx'] >= {params['min_adx']}]\n\n"

    if params.get('use_freshness_filter', False):
        code += f"    # Zone Freshness Filter\n"
        code += f"    filtered_df = filtered_df[filtered_df['zone_freshness'] >= {params['min_freshness']}]\n\n"

    if params.get('use_quality_filter', False):
        code += f"    # Zone Quality Filter\n"
        code += f"    filtered_df = filtered_df[filtered_df['zone_quality'] >= {params['min_zone_quality']}]\n\n"

    if params.get('use_liquidity_filter', False):
        liquidity_value = params.get('require_liquidity_sweep')
        code += f"    # Liquidity Sweep Filter\n"
        code += f"    filtered_df = filtered_df[filtered_df['liquidity_swept'] == {liquidity_value}]\n\n"

    code += f"    # Ensure minimum trade count for statistical significance\n"
    code += f"    if len(filtered_df) < {params.get('min_trades_threshold', 20)}:\n"
    code += f"        print(f'Warning: Only {{len(filtered_df)}} trades pass filters. Results may not be statistically significant.')\n\n"

    code += '''    return filtered_df


# Example usage:
if __name__ == "__main__":
    # Load your trading signals
    # df = load_trading_signals()

    # Apply optimal filters
    # filtered_signals = apply_optimal_filters(df)

    # Use filtered signals for trading
    # print(f"Filtered from {len(df)} to {len(filtered_signals)} high-quality signals")
    pass
'''

    # Save to file
    with open('apply_optimal_filters.py', 'w') as f:
        f.write(code)

    print("✓ Filter function saved to apply_optimal_filters.py")


if __name__ == "__main__":
    main()
