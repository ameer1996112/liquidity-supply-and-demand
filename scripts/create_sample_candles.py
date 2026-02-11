"""Create sample XAUUSD M5 candles for backtest testing."""
import pandas as pd
from pathlib import Path
from datetime import datetime, timezone, timedelta

def main():
    base = datetime(2026, 1, 1, 0, 0, 0, tzinfo=timezone.utc)
    n = 5000  # ~17 days of M5
    import numpy as np
    np.random.seed(42)
    price = 2650.0
    rows = []
    for i in range(n):
        t = base + timedelta(minutes=5 * i)
        change = np.random.randn() * 2
        price = max(2600, min(2700, price + change))
        o = price
        h = price + abs(np.random.randn() * 1.5)
        l = price - abs(np.random.randn() * 1.5)
        c = price + np.random.randn() * 0.5
        rows.append({"time": t, "open": o, "high": max(o, h, c), "low": min(o, l, c), "close": c, "volume": 100})
    df = pd.DataFrame(rows)
    df["high"] = df[["open", "high", "close"]].max(axis=1)
    df["low"] = df[["open", "low", "close"]].min(axis=1)
    out = Path("data/backtest_candles/XAUUSD/M5/2026-01-01_2026-02-10.csv")
    out.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(out, index=False)
    print(f"Saved {len(df)} candles to {out}")

if __name__ == "__main__":
    main()
