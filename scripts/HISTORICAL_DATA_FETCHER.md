# MetaAPI Historical Data Fetcher

Fetch historical candle data from MetaAPI for any symbol and timeframe.

## Features

✅ **Multiple Symbols:** Fetch data for multiple symbols in one run (e.g., EURUSD, XAUUSD, GBPUSD)
✅ **Multiple Timeframes:** Support for up to 5 timeframes simultaneously (1m, 5m, 15m, 1h, 4h, 1d, etc.)
✅ **Flexible Date Range:** Specify any start/end date
✅ **Auto-save to CSV:** Organized by symbol/timeframe with timestamps
✅ **Retry Logic:** Automatic retries on failures with exponential backoff
✅ **Rate Limiting:** Built-in rate limit handling (429 responses)
✅ **Progress Indicators:** Real-time progress tracking

## Requirements

The script uses your **Vantage account** credentials from `.env`:
- `META_API_TOKEN_VANTAGE`
- `META_API_ACCOUNT_ID_VANTAGE`

These are already configured in your `.env` file ✅

## Supported Timeframes

| Timeframe | MetaAPI Format |
|-----------|---------------|
| 1m        | 1-minute      |
| 5m        | 5-minute      |
| 15m       | 15-minute     |
| 30m       | 30-minute     |
| 1h        | 1-hour        |
| 4h        | 4-hour        |
| 1d        | 1-day         |
| 1w        | 1-week        |
| 1M        | 1-month       |

## Usage

### Basic Syntax

```bash
python scripts/fetch_historical_data.py \
  --symbol SYMBOL1,SYMBOL2 \
  --timeframes TF1,TF2,TF3 \
  --start YYYY-MM-DD \
  --end YYYY-MM-DD \
  [--output OUTPUT_DIR] \
  [--region REGION]
```

### Examples

#### 1. Single Symbol, Single Timeframe

```bash
# Fetch EURUSD 1-hour data for 2024
python scripts/fetch_historical_data.py \
  --symbol EURUSD \
  --timeframes 1h \
  --start 2024-01-01 \
  --end 2024-02-11
```

#### 2. Single Symbol, Multiple Timeframes

```bash
# Fetch XAUUSD on 5 different timeframes
python scripts/fetch_historical_data.py \
  --symbol XAUUSD \
  --timeframes 1m,5m,15m,1h,4h \
  --start 2024-01-01 \
  --end 2024-02-11
```

#### 3. Multiple Symbols, Multiple Timeframes

```bash
# Fetch multiple forex pairs on 3 timeframes
python scripts/fetch_historical_data.py \
  --symbol EURUSD,GBPUSD,USDJPY,XAUUSD \
  --timeframes 1h,4h,1d \
  --start 2023-01-01 \
  --end 2024-02-11
```

#### 4. Custom Output Directory

```bash
# Save to custom directory (e.g., for backtesting)
python scripts/fetch_historical_data.py \
  --symbol EURUSD \
  --timeframes 1h \
  --start 2024-01-01 \
  --end 2024-02-11 \
  --output data/backtest/EURUSD
```

#### 5. Specific Date Range with Time

```bash
# Include specific time (for intraday analysis)
python scripts/fetch_historical_data.py \
  --symbol XAUUSD \
  --timeframes 1m,5m \
  --start "2024-02-01 00:00:00" \
  --end "2024-02-01 23:59:59"
```

## Output Format

### Directory Structure

```
data/historical/
├── EURUSD/
│   ├── EURUSD_1h_20240101_20240211.csv
│   ├── EURUSD_4h_20240101_20240211.csv
│   └── EURUSD_1d_20240101_20240211.csv
├── XAUUSD/
│   ├── XAUUSD_1m_20240101_20240211.csv
│   ├── XAUUSD_5m_20240101_20240211.csv
│   └── XAUUSD_15m_20240101_20240211.csv
└── GBPUSD/
    └── GBPUSD_1h_20240101_20240211.csv
```

### CSV Format

Each CSV file contains the following columns:

| Column | Description              |
|--------|--------------------------|
| time   | Timestamp (UTC)          |
| open   | Opening price            |
| high   | Highest price            |
| low    | Lowest price             |
| close  | Closing price            |
| volume | Tick volume              |

Example:
```csv
time,open,high,low,close,volume
2024-01-01 00:00:00,1.10523,1.10542,1.10501,1.10518,1245
2024-01-01 01:00:00,1.10518,1.10567,1.10512,1.10551,982
```

## Logs

The script creates two types of logs:

1. **Console Output:** Real-time progress and status updates
2. **Log File:** `fetch_historical_data.log` (detailed logs including errors)

Example log output:
```
================================================================================
MetaAPI Historical Data Fetcher
================================================================================
Symbols: EURUSD, XAUUSD
Timeframes: 1h, 4h, 1d
Date Range: 2024-01-01 to 2024-02-11
Output Dir: data/historical
================================================================================

[1/6] Processing EURUSD 1h...
✅ Fetched 1008 candles for EURUSD 1h
💾 Saved to: data/historical/EURUSD/EURUSD_1h_20240101_20240211.csv

[2/6] Processing EURUSD 4h...
✅ Fetched 252 candles for EURUSD 4h
💾 Saved to: data/historical/EURUSD/EURUSD_4h_20240101_20240211.csv
```

## Rate Limits

MetaAPI has rate limits. The script handles this automatically:

- **429 Response:** Waits 60 seconds before retrying
- **Request Spacing:** 1 second delay between requests
- **Retry Logic:** Up to 3 attempts with exponential backoff

If you hit rate limits frequently, consider:
- Reducing the number of symbols/timeframes per run
- Splitting large date ranges into smaller chunks
- Upgrading your MetaAPI plan for higher limits

## Error Handling

The script includes comprehensive error handling:

✅ Invalid timeframes → Clear error message with valid options
✅ Network timeouts → Automatic retry with backoff
✅ Server errors (5xx) → Retry up to 3 times
✅ Missing credentials → Clear error message
✅ Invalid date format → Helpful error with format examples

## Common Symbols

### Forex Majors
- EURUSD, GBPUSD, USDJPY, USDCHF, AUDUSD, NZDUSD, USDCAD

### Forex JPY Crosses
- EURJPY, GBPJPY, CHFJPY, AUDJPY, NZDJPY, CADJPY

### Precious Metals
- XAUUSD (Gold), XAGUSD (Silver)

### Indices
- US30 (Dow Jones), NAS100 (Nasdaq), SPX500 (S&P 500)

### Crypto (if supported)
- BTCUSD, ETHUSD

> **Note:** Symbol availability depends on your broker (Vantage). Check MetaTrader 5 Market Watch for exact symbol names.

## Tips

1. **Start Small:** Test with a single symbol/timeframe first
2. **Check Symbol Names:** Verify exact symbol names in MT5 (e.g., some brokers use "XAUUSD.m" instead of "XAUUSD")
3. **Date Range:** Start with 1-3 months for initial tests
4. **Timeframe Selection:** Choose timeframes based on your trading strategy
5. **CSV Integration:** Use the output CSVs for backtesting, analysis, or ML model training

## Troubleshooting

### "Missing required environment variables"
- Ensure `META_API_TOKEN_VANTAGE` and `META_API_ACCOUNT_ID_VANTAGE` are in your `.env` file
- Run `source .env` or restart your terminal

### "No data returned for SYMBOL"
- Verify symbol name in MT5 Market Watch
- Check date range (data may not be available for very old dates)
- Ensure your account has market data access

### "Rate limited (429)"
- Script automatically waits 60 seconds
- Consider reducing concurrent requests
- Check your MetaAPI plan limits

### "Failed to fetch after 3 retries"
- Check your internet connection
- Verify MetaAPI service status
- Try reducing the date range (smaller chunks)

## Advanced Usage

### Batch Processing Multiple Date Ranges

```bash
# Fetch 2023 data
python scripts/fetch_historical_data.py \
  --symbol EURUSD \
  --timeframes 1h,4h \
  --start 2023-01-01 \
  --end 2023-12-31

# Fetch 2024 data
python scripts/fetch_historical_data.py \
  --symbol EURUSD \
  --timeframes 1h,4h \
  --start 2024-01-01 \
  --end 2024-02-11
```

### Using Different Regions

```bash
# Use London region for lower latency (if you're in Europe)
python scripts/fetch_historical_data.py \
  --symbol EURUSD \
  --timeframes 1h \
  --start 2024-01-01 \
  --end 2024-02-11 \
  --region london
```

Available regions:
- `new-york` (default)
- `london`
- `singapore`

## Integration with Backtesting

The fetched data can be used directly with your backtesting system:

```bash
# 1. Fetch historical data
python scripts/fetch_historical_data.py \
  --symbol XAUUSD \
  --timeframes 1h \
  --start 2024-01-01 \
  --end 2024-02-11 \
  --output data/backtest/XAUUSD

# 2. Run backtest (if you have a backtesting script)
python scripts/run_backtest.py \
  --data data/backtest/XAUUSD/XAUUSD_1h_20240101_20240211.csv \
  --strategy SND_Strategy
```

## Support

For MetaAPI-specific issues:
- [MetaAPI Documentation](https://metaapi.cloud/docs/)
- [MetaAPI Support](https://metaapi.cloud/support/)

For script issues:
- Check `fetch_historical_data.log` for detailed error messages
- Run with `--help` to see all available options
