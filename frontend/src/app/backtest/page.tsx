'use client';

import { useState } from 'react';
import dynamic from 'next/dynamic';
import { useMutation } from '@tanstack/react-query';
import { Trade } from '@/components/backtest/BacktestChart';
import { Card } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { Badge } from '@/components/ui/badge';
import { ClientDate } from '@/components/ui/ClientDate';
import { Skeleton } from '@/components/ui/skeleton';
import {
  Play,
  TrendingUp,
  TrendingDown,
  DollarSign,
  Target,
  AlertCircle,
} from 'lucide-react';
import { CandlestickData, Time } from 'lightweight-charts';
import { backtestAPI } from '@/lib/api';

const BacktestChart = dynamic(
  () =>
    import('@/components/backtest/BacktestChart').then((m) => m.BacktestChart),
  {
    loading: () => (
      <Skeleton className='h-[600px] w-full rounded-lg bg-[var(--to-surface-raised)]/60' />
    ),
  },
);

const FXReplayController = dynamic(
  () =>
    import('@/components/backtest/FXReplayController').then(
      (m) => m.FXReplayController,
    ),
  {
    loading: () => (
      <Skeleton className='h-24 w-full rounded-lg bg-[var(--to-surface-raised)]/60 mt-4' />
    ),
  },
);

const BacktestPerformanceTab = dynamic(
  () =>
    import('@/components/backtest/BacktestPerformanceTab').then(
      (m) => m.BacktestPerformanceTab,
    ),
  {
    loading: () => (
      <Skeleton className='h-80 w-full rounded-lg bg-[var(--to-surface-raised)]/60' />
    ),
  },
);

// API Types
interface BacktestRequest {
  symbol: string;
  start_date: string;
  end_date: string;
  timeframe: string;
  initial_cash: number;
  commission: number;
  risk_percent: number;
  min_rr_ratio: number;
  zone_lookback?: number;
  stop_buffer_pips?: number;
  require_liquidity_sweep?: boolean;
  reject_compression_arrival?: boolean;
  require_structure_break?: boolean;
  liq_entry_max_dist?: number;
  ai_quality_threshold?: number;
  min_entry_grade?: string;
  max_bars_in_trade?: number;
}

interface BacktestResponse {
  success: boolean;
  candles: Array<{
    time: number;
    open: number;
    high: number;
    low: number;
    close: number;
    volume: number;
  }>;
  trades: Trade[];
  equity_curve: Array<{ time: number; equity: number }>;
  stats: {
    total_trades: number;
    winning_trades: number;
    losing_trades: number;
    win_rate: number;
    total_return: number;
    sharpe_ratio: number;
    max_drawdown: number;
    profit_factor: number;
    avg_win: number;
    avg_loss: number;
    largest_win: number;
    largest_loss: number;
  };
  symbol: string;
  timeframe: string;
  initial_cash: number;
  final_equity: number;
  candles_count: number;
}

export default function BacktestPage() {
  const [currentCandleIndex, setCurrentCandleIndex] = useState(0);
  const [backtestResult, setBacktestResult] = useState<BacktestResponse | null>(
    null,
  );
  const [replayMode, setReplayMode] = useState(false); // Replay mode OFF by default

  // Backtest configuration (matches Pine Aggressive profile)
  const [config, setConfig] = useState<BacktestRequest>({
    symbol: 'XAUUSD',
    start_date: '2026-01-01',
    end_date: '2026-02-12',
    timeframe: '5m',
    initial_cash: 10000,
    commission: 0.0002,
    risk_percent: 0.5,
    min_rr_ratio: 1.5, // ← Changed from 2.0 to match Pine Aggressive
    zone_lookback: 20, // ← Zone detection lookback period
    stop_buffer_pips: 1.0, // ← Stop loss buffer (from Pine default)
    require_liquidity_sweep: true, // ← Changed from false (Pine always requires this)
    reject_compression_arrival: false, // ← Changed from true (let more trades through)
    require_structure_break: false,
    // Advanced liquidity & quality settings
    liq_entry_max_dist: 500.0, // Max liquidity distance (pips) - 500 for gold, 50 for forex
    ai_quality_threshold: 60, // Min AI quality score (0-100)
    min_entry_grade: 'C+', // Min zone grade (A+, A, B+, B, C+, C)
    max_bars_in_trade: 0, // Max bars before auto-exit (0=disabled, Pine-style)
  });

  // Run backtest mutation (uses Railway URL in production)
  const runBacktestMutation = useMutation({
    mutationFn: async (request: BacktestRequest) => {
      return backtestAPI.runBacktest(request);
    },
    onSuccess: (data) => {
      setBacktestResult(data);
      setCurrentCandleIndex(0);
    },
  });

  const handleRunBacktest = () => {
    runBacktestMutation.mutate(config);
  };

  // Convert candles to lightweight-charts format
  // If replay mode is OFF, show ALL candles; if ON, show only up to currentCandleIndex
  const chartCandles: CandlestickData<Time>[] =
    backtestResult?.candles
      .slice(0, replayMode ? currentCandleIndex + 1 : undefined)
      .map((candle) => ({
        time: candle.time as Time,
        open: candle.open,
        high: candle.high,
        low: candle.low,
        close: candle.close,
        volume: candle.volume,
      })) || [];

  // Filter trades visible up to current candle (only in replay mode)
  const lastCandleTime = chartCandles[chartCandles.length - 1]?.time;
  const visibleTrades =
    backtestResult?.trades.filter((trade) => {
      if (!lastCandleTime) return false;
      // In replay mode, filter by current candle time; otherwise show all trades
      if (replayMode) {
        return (
          trade.entry_time <=
          (typeof lastCandleTime === 'number'
            ? lastCandleTime
            : Number(lastCandleTime))
        );
      }
      return true; // Show all trades when not in replay mode
    }) || [];

  const stats = backtestResult?.stats;

  return (
    <div className='space-y-4 animate-fade-in-up'>
      {/* Header */}
      <div className='flex items-start justify-between gap-3'>
        <div>
          <h1 className='page-title text-lg font-semibold'>Backtest Lab</h1>
          <p className='page-subtitle mt-0.5 text-xs'>
            5m zone strategy backtesting with FX Replay visualization
          </p>
        </div>
        <span className='tf-badge'>5M</span>
      </div>

      {/* Configuration Panel */}
      <div className='glow-card'>
        <div className='tv-divider flex items-center justify-between border-b px-3 py-2'>
          <span className='panel-label'>Configuration</span>
          <div className='flex gap-2'>
            <Button
              variant={config.min_rr_ratio === 2.0 ? 'default' : 'outline'}
              size='sm'
              onClick={() =>
                setConfig({
                  ...config,
                  risk_percent: 0.5,
                  min_rr_ratio: 2.0,
                  zone_lookback: 20,
                  stop_buffer_pips: 1.0,
                  require_liquidity_sweep: true,
                  reject_compression_arrival: true,
                  require_structure_break: false,
                  liq_entry_max_dist: 50.0,
                  ai_quality_threshold: 70,
                  min_entry_grade: 'B+',
                  max_bars_in_trade: 100,
                })
              }
            >
              Balanced
            </Button>
            <Button
              variant={config.min_rr_ratio === 1.5 ? 'default' : 'outline'}
              size='sm'
              onClick={() =>
                setConfig({
                  ...config,
                  risk_percent: 0.5,
                  min_rr_ratio: 1.5,
                  zone_lookback: 20,
                  stop_buffer_pips: 1.0,
                  require_liquidity_sweep: true,
                  reject_compression_arrival: false,
                  require_structure_break: false,
                  liq_entry_max_dist: 500.0,
                  ai_quality_threshold: 60,
                  min_entry_grade: 'C+',
                  max_bars_in_trade: 200,
                })
              }
            >
              Aggressive
            </Button>
          </div>
        </div>
        <div className='grid grid-cols-2 md:grid-cols-4 gap-4'>
          <div>
            <label className='mb-2 block text-sm text-[var(--to-text-dim)]'>Symbol</label>
            <select
              value={config.symbol}
              onChange={(e) => setConfig({ ...config, symbol: e.target.value })}
              className='w-full rounded-md border border-[var(--to-border)] bg-[var(--to-surface)] px-3 py-2 text-[var(--to-text-primary)]'
            >
              <optgroup label='Forex - Majors'>
                <option value='EURUSD'>EUR/USD - Euro vs US Dollar</option>
                <option value='GBPUSD'>
                  GBP/USD - British Pound vs US Dollar
                </option>
                <option value='USDJPY'>
                  USD/JPY - US Dollar vs Japanese Yen
                </option>
                <option value='USDCHF'>
                  USD/CHF - US Dollar vs Swiss Franc
                </option>
                <option value='AUDUSD'>
                  AUD/USD - Australian Dollar vs US Dollar
                </option>
                <option value='NZDUSD'>
                  NZD/USD - New Zealand Dollar vs US Dollar
                </option>
                <option value='USDCAD'>
                  USD/CAD - US Dollar vs Canadian Dollar
                </option>
              </optgroup>
              <optgroup label='Forex - Crosses'>
                <option value='EURGBP'>EUR/GBP - Euro vs British Pound</option>
                <option value='EURJPY'>EUR/JPY - Euro vs Japanese Yen</option>
                <option value='GBPJPY'>
                  GBP/JPY - British Pound vs Japanese Yen
                </option>
                <option value='AUDJPY'>
                  AUD/JPY - Australian Dollar vs Japanese Yen
                </option>
              </optgroup>
              <optgroup label='Metals'>
                <option value='XAUUSD'>XAU/USD - Gold vs US Dollar</option>
                <option value='XAGUSD'>XAG/USD - Silver vs US Dollar</option>
              </optgroup>
              <optgroup label='Indices'>
                <option value='NAS100'>NAS100 - NASDAQ 100</option>
                <option value='US30'>US30 - Dow Jones 30</option>
                <option value='SPX500'>SPX500 - S&P 500</option>
              </optgroup>
              <optgroup label='Crypto'>
                <option value='BTCUSD'>BTC/USD - Bitcoin vs US Dollar</option>
                <option value='ETHUSD'>ETH/USD - Ethereum vs US Dollar</option>
              </optgroup>
            </select>
          </div>

          <div>
            <label className='mb-2 block text-sm text-[var(--to-text-dim)]'>
              Start Date
            </label>
            <input
              type='date'
              value={config.start_date}
              onChange={(e) =>
                setConfig({ ...config, start_date: e.target.value })
              }
              className='w-full rounded-md border border-[var(--to-border)] bg-[var(--to-surface)] px-3 py-2 text-[var(--to-text-primary)]'
            />
          </div>

          <div>
            <label className='mb-2 block text-sm text-[var(--to-text-dim)]'>
              End Date
            </label>
            <input
              type='date'
              value={config.end_date}
              onChange={(e) =>
                setConfig({ ...config, end_date: e.target.value })
              }
              className='w-full rounded-md border border-[var(--to-border)] bg-[var(--to-surface)] px-3 py-2 text-[var(--to-text-primary)]'
            />
          </div>

          <div>
            <label className='mb-2 block text-sm text-[var(--to-text-dim)]'>
              Timeframe
            </label>
            <select
              value={config.timeframe}
              onChange={(e) =>
                setConfig({ ...config, timeframe: e.target.value })
              }
              className='w-full rounded-md border border-[var(--to-border)] bg-[var(--to-surface)] px-3 py-2 text-[var(--to-text-primary)]'
            >
              <option value='5m'>5 Minutes</option>
              <option value='15m'>15 Minutes</option>
              <option value='1h'>1 Hour</option>
              <option value='4h'>4 Hours</option>
              <option value='1d'>1 Day</option>
            </select>
          </div>
        </div>

        {/* Risk & Strategy Parameters */}
        <div className='mt-4 grid grid-cols-2 md:grid-cols-3 gap-4'>
          <div>
            <label className='mb-2 block text-sm text-[var(--to-text-dim)]'>
              Risk Per Trade (%)
            </label>
            <input
              type='number'
              value={config.risk_percent}
              onChange={(e) =>
                setConfig({
                  ...config,
                  risk_percent: parseFloat(e.target.value) || 0.5,
                })
              }
              min='0.1'
              max='5.0'
              step='0.1'
              className='w-full rounded-md border border-[var(--to-border)] bg-[var(--to-surface)] px-3 py-2 text-[var(--to-text-primary)]'
            />
          </div>

          <div>
            <label className='mb-2 block text-sm text-[var(--to-text-dim)]'>
              Min R:R Ratio
            </label>
            <input
              type='number'
              value={config.min_rr_ratio}
              onChange={(e) =>
                setConfig({
                  ...config,
                  min_rr_ratio: parseFloat(e.target.value) || 1.5,
                })
              }
              min='0.5'
              max='10.0'
              step='0.1'
              className='w-full rounded-md border border-[var(--to-border)] bg-[var(--to-surface)] px-3 py-2 text-[var(--to-text-primary)]'
            />
          </div>

          <div>
            <label className='mb-2 block text-sm text-[var(--to-text-dim)]'>
              Zone Lookback (bars)
            </label>
            <input
              type='number'
              value={config.zone_lookback}
              onChange={(e) =>
                setConfig({
                  ...config,
                  zone_lookback: parseInt(e.target.value) || 20,
                })
              }
              min='5'
              max='50'
              step='1'
              className='w-full rounded-md border border-[var(--to-border)] bg-[var(--to-surface)] px-3 py-2 text-[var(--to-text-primary)]'
            />
          </div>

          <div>
            <label className='mb-2 block text-sm text-[var(--to-text-dim)]'>
              SL Buffer (pips)
            </label>
            <input
              type='number'
              value={config.stop_buffer_pips}
              onChange={(e) =>
                setConfig({
                  ...config,
                  stop_buffer_pips: parseFloat(e.target.value) || 1.0,
                })
              }
              min='0'
              max='10.0'
              step='0.1'
              className='w-full rounded-md border border-[var(--to-border)] bg-[var(--to-surface)] px-3 py-2 text-[var(--to-text-primary)]'
            />
          </div>

          <div>
            <label className='mb-2 block text-sm text-[var(--to-text-dim)]'>
              Initial Cash ($)
            </label>
            <input
              type='number'
              value={config.initial_cash}
              onChange={(e) =>
                setConfig({
                  ...config,
                  initial_cash: parseFloat(e.target.value) || 10000,
                })
              }
              min='100'
              step='1000'
              className='w-full rounded-md border border-[var(--to-border)] bg-[var(--to-surface)] px-3 py-2 text-[var(--to-text-primary)]'
            />
          </div>

          <div>
            <label className='mb-2 block text-sm text-[var(--to-text-dim)]'>
              Commission
            </label>
            <input
              type='number'
              value={config.commission}
              onChange={(e) =>
                setConfig({
                  ...config,
                  commission: parseFloat(e.target.value) || 0.0002,
                })
              }
              min='0'
              max='0.01'
              step='0.0001'
              className='w-full rounded-md border border-[var(--to-border)] bg-[var(--to-surface)] px-3 py-2 text-[var(--to-text-primary)]'
            />
          </div>
        </div>

        {/* AI Guardian Filters */}
        <div className='mt-4 flex gap-4'>
          <label className='flex items-center gap-2 cursor-pointer'>
            <input
              type='checkbox'
              checked={config.require_liquidity_sweep || false}
              onChange={(e) =>
                setConfig({
                  ...config,
                  require_liquidity_sweep: e.target.checked,
                })
              }
              className='rounded cursor-pointer'
            />
            <span className='text-sm'>Require Liquidity Sweep</span>
          </label>

          <label className='flex items-center gap-2 cursor-pointer'>
            <input
              type='checkbox'
              checked={config.reject_compression_arrival || false}
              onChange={(e) =>
                setConfig({
                  ...config,
                  reject_compression_arrival: e.target.checked,
                })
              }
              className='rounded cursor-pointer'
            />
            <span className='text-sm'>Reject Compression</span>
          </label>

          <label className='flex items-center gap-2 cursor-pointer'>
            <input
              type='checkbox'
              checked={config.require_structure_break || false}
              onChange={(e) =>
                setConfig({
                  ...config,
                  require_structure_break: e.target.checked,
                })
              }
              className='rounded cursor-pointer'
            />
            <span className='text-sm'>Require Structure Break</span>
          </label>
        </div>

        {/* Advanced Liquidity & Quality Settings */}
        <div className='mt-4'>
          <h3 className='mb-3 text-sm font-semibold text-[var(--to-text-secondary)]'>
            Advanced Settings (Liquidity &amp; AI Quality)
          </h3>
          <div className='grid grid-cols-2 md:grid-cols-4 gap-4'>
            <div>
              <label className='mb-2 block text-sm text-[var(--to-text-dim)]'>
                Max Liquidity Distance (pips)
              </label>
              <input
                type='number'
                value={config.liq_entry_max_dist}
                onChange={(e) =>
                  setConfig({
                    ...config,
                    liq_entry_max_dist: parseFloat(e.target.value) || 500.0,
                  })
                }
                min='10'
                max='1000'
                step='10'
                className='w-full rounded-md border border-[var(--to-border)] bg-[var(--to-surface)] px-3 py-2 text-[var(--to-text-primary)]'
              />
              <p className='mt-1 text-xs text-[var(--to-text-secondary)]'>
                Max distance from zone to liquidity level
              </p>
            </div>

            <div>
              <label className='mb-2 block text-sm text-[var(--to-text-dim)]'>
                AI Quality Threshold (0-100)
              </label>
              <input
                type='number'
                value={config.ai_quality_threshold}
                onChange={(e) =>
                  setConfig({
                    ...config,
                    ai_quality_threshold: parseInt(e.target.value) || 60,
                  })
                }
                min='0'
                max='100'
                step='5'
                className='w-full rounded-md border border-[var(--to-border)] bg-[var(--to-surface)] px-3 py-2 text-[var(--to-text-primary)]'
              />
              <p className='mt-1 text-xs text-[var(--to-text-secondary)]'>
                Minimum AI quality score to enter trade
              </p>
            </div>

            <div>
              <label className='mb-2 block text-sm text-[var(--to-text-dim)]'>
                Minimum Entry Grade
              </label>
              <select
                value={config.min_entry_grade}
                onChange={(e) =>
                  setConfig({ ...config, min_entry_grade: e.target.value })
                }
                className='w-full rounded-md border border-[var(--to-border)] bg-[var(--to-surface)] px-3 py-2 text-[var(--to-text-primary)]'
              >
                <option value='A+'>A+ (90-100)</option>
                <option value='A'>A (80-89)</option>
                <option value='B+'>B+ (70-79)</option>
                <option value='B'>B (60-69)</option>
                <option value='C+'>C+ (50-59)</option>
                <option value='C'>C (0-49)</option>
              </select>
              <p className='mt-1 text-xs text-[var(--to-text-secondary)]'>
                Minimum zone grade to enter trade
              </p>
            </div>

            <div>
              <label className='mb-2 block text-sm text-[var(--to-text-dim)]'>
                Max Bars in Trade
              </label>
              <input
                type='number'
                value={config.max_bars_in_trade}
                onChange={(e) =>
                  setConfig({
                    ...config,
                    max_bars_in_trade: parseInt(e.target.value) || 0,
                  })
                }
                min='0'
                max='500'
                step='10'
                className='w-full rounded-md border border-[var(--to-border)] bg-[var(--to-surface)] px-3 py-2 text-[var(--to-text-primary)]'
              />
              <p className='mt-1 text-xs text-[var(--to-text-secondary)]'>
                Auto-exit after N bars (0=disabled)
              </p>
            </div>
          </div>
        </div>

        <Button
          onClick={handleRunBacktest}
          disabled={runBacktestMutation.isPending}
          className='mt-4'
          size='lg'
        >
          <Play className='h-4 w-4 mr-2' />
          {runBacktestMutation.isPending
            ? 'Running Backtest...'
            : 'Run Backtest'}
        </Button>
      </div>

      {/* Results */}
      {backtestResult && (
        <>
          {/* Stats Cards */}
          <div className='grid grid-cols-2 md:grid-cols-4 gap-3'>
            <div className='glow-card p-3'>
              <div className='flex items-center gap-1.5 mb-1.5'>
                <Target className='h-3.5 w-3.5 text-indigo-400' />
                <span className='panel-label'>Total Trades</span>
              </div>
              <p
                className='text-xl font-bold tabular-nums text-[var(--to-text-primary)]'
                style={{ fontFamily: 'var(--font-mono)' }}
              >
                {stats?.total_trades}
              </p>
            </div>

            <div className='glow-card p-3'>
              <div className='flex items-center gap-1.5 mb-1.5'>
                <TrendingUp className='h-3.5 w-3.5 text-[var(--to-long)]' />
                <span className='panel-label'>Win Rate</span>
              </div>
              <p
                className='text-xl font-bold tabular-nums text-[var(--to-long)]'
                style={{ fontFamily: 'var(--font-mono)' }}
              >
                {stats?.win_rate.toFixed(1)}%
              </p>
            </div>

            <div className='glow-card p-3'>
              <div className='flex items-center gap-1.5 mb-1.5'>
                <DollarSign className='h-3.5 w-3.5 text-amber-400' />
                <span className='panel-label'>Total Return</span>
              </div>
              <p
                className={`text-xl font-bold tabular-nums ${
                  (stats?.total_return || 0) >= 0
                    ? 'text-[var(--to-long)]'
                    : 'text-[var(--to-short)]'
                }`}
                style={{ fontFamily: 'var(--font-mono)' }}
              >
                {stats?.total_return.toFixed(2)}%
              </p>
            </div>

            <div className='glow-card p-3'>
              <div className='flex items-center gap-1.5 mb-1.5'>
                <TrendingDown className='h-3.5 w-3.5 text-[var(--to-short)]' />
                <span className='panel-label'>Max Drawdown</span>
              </div>
              <p
                className='text-xl font-bold tabular-nums text-[var(--to-short)]'
                style={{ fontFamily: 'var(--font-mono)' }}
              >
                {stats?.max_drawdown.toFixed(2)}%
              </p>
            </div>
          </div>

          {/* Chart, Trades, Performance Tabs */}
          <Tabs defaultValue='chart' className='w-full'>
            <TabsList className='grid w-full grid-cols-3'>
              <TabsTrigger value='chart'>Chart</TabsTrigger>
              <TabsTrigger value='trades'>Trade List</TabsTrigger>
              <TabsTrigger value='performance'>Performance</TabsTrigger>
            </TabsList>

            <TabsContent value='chart' className='mt-4'>
              <Card className='glow-card p-6'>
                <div className='flex justify-between items-center mb-4'>
                  <h2 className='text-xl font-semibold'>Backtest Chart</h2>
                  <Button
                    variant={replayMode ? 'default' : 'outline'}
                    size='sm'
                    onClick={() => {
                      setReplayMode(!replayMode);
                      if (!replayMode) {
                        setCurrentCandleIndex(0);
                      }
                    }}
                  >
                    <Play className='h-4 w-4 mr-2' />
                    {replayMode ? 'Exit Replay Mode' : 'Enable FX Replay'}
                  </Button>
                </div>

                <BacktestChart
                  candles={chartCandles}
                  trades={visibleTrades}
                  height={600}
                />

                {replayMode && (
                  <div className='mt-4'>
                    <FXReplayController
                      candles={
                        backtestResult.candles as unknown as CandlestickData<Time>[]
                      }
                      currentIndex={currentCandleIndex}
                      onCandleIndexChange={setCurrentCandleIndex}
                    />
                  </div>
                )}
              </Card>
            </TabsContent>

            <TabsContent value='trades' className='mt-4'>
              <Card className='glow-card p-6'>
                <h2 className='text-xl font-semibold mb-4'>
                  Trade List ({visibleTrades.length} trades)
                </h2>
                <div className='overflow-x-auto'>
                  <table className='w-full text-sm'>
                    <thead className='border-b border-[var(--to-border)]'>
                      <tr className='text-[var(--to-text-dim)]'>
                        <th className='text-left py-3 px-2'>#</th>
                        <th className='text-left py-3 px-2'>Type</th>
                        <th className='text-left py-3 px-2'>Entry Date</th>
                        <th className='text-left py-3 px-2'>Exit Date</th>
                        <th className='text-right py-3 px-2'>Duration</th>
                        <th className='text-right py-3 px-2'>Entry Price</th>
                        <th className='text-right py-3 px-2'>Exit Price</th>
                        <th className='text-right py-3 px-2'>Size</th>
                        <th className='text-right py-3 px-2'>Profit $</th>
                        <th className='text-right py-3 px-2'>Profit %</th>
                        <th className='text-right py-3 px-2'>Return %</th>
                      </tr>
                    </thead>
                    <tbody>
                      {visibleTrades.map((trade, index) => {
                        const duration =
                          (trade.exit_time - trade.entry_time) / 60; // minutes
                        const durationText =
                          duration < 60
                            ? `${Math.floor(duration)}m`
                            : `${Math.floor(duration / 60)}h ${Math.floor(
                                duration % 60,
                              )}m`;

                        return (
                          <tr
                            key={index}
                            className='border-b border-[var(--to-border)] hover:bg-[var(--to-surface-raised)]/50 transition-colors'
                          >
                            <td className='py-3 px-2 text-[var(--to-text-secondary)]'>
                              {index + 1}
                            </td>
                            <td className='py-3 px-2'>
                              <Badge
                                variant={
                                  trade.side === 'long'
                                    ? 'default'
                                    : 'destructive'
                                }
                                className='text-xs'
                              >
                                {trade.side === 'long' ? 'LONG' : 'SHORT'}
                              </Badge>
                            </td>
                            <td className='py-3 px-2 text-[var(--to-text-dim)] text-xs'>
                              <ClientDate
                                render={() =>
                                  new Date(
                                    trade.entry_time * 1000,
                                  ).toLocaleString('en-US', {
                                    month: 'short',
                                    day: 'numeric',
                                    hour: '2-digit',
                                    minute: '2-digit',
                                  })
                                }
                              />
                            </td>
                            <td className='py-3 px-2 text-[var(--to-text-dim)] text-xs'>
                              <ClientDate
                                render={() =>
                                  new Date(
                                    trade.exit_time * 1000,
                                  ).toLocaleString('en-US', {
                                    month: 'short',
                                    day: 'numeric',
                                    hour: '2-digit',
                                    minute: '2-digit',
                                  })
                                }
                              />
                            </td>
                            <td className='py-3 px-2 text-right text-[var(--to-text-dim)] text-xs'>
                              {durationText}
                            </td>
                            <td className='py-3 px-2 text-right text-[var(--to-text-secondary)]'>
                              {trade.entry_price.toFixed(5)}
                            </td>
                            <td className='py-3 px-2 text-right text-[var(--to-text-secondary)]'>
                              {trade.exit_price.toFixed(5)}
                            </td>
                            <td className='py-3 px-2 text-right text-[var(--to-text-dim)]'>
                              {trade.size.toFixed(2)}
                            </td>
                            <td
                              className={`py-3 px-2 text-right font-semibold ${
                                trade.pnl >= 0
                                  ? 'text-[var(--to-long)]'
                                  : 'text-[var(--to-short)]'
                              }`}
                            >
                              {trade.pnl >= 0 ? '+' : ''}
                              {trade.pnl.toFixed(2)}
                            </td>
                            <td
                              className={`py-3 px-2 text-right font-semibold ${
                                trade.pnl_percent >= 0
                                  ? 'text-[var(--to-long)]'
                                  : 'text-[var(--to-short)]'
                              }`}
                            >
                              {trade.pnl_percent >= 0 ? '+' : ''}
                              {trade.pnl_percent.toFixed(2)}%
                            </td>
                            <td
                              className={`py-3 px-2 text-right font-semibold ${
                                trade.return_pct >= 0
                                  ? 'text-[var(--to-long)]'
                                  : 'text-[var(--to-short)]'
                              }`}
                            >
                              {trade.return_pct >= 0 ? '+' : ''}
                              {trade.return_pct.toFixed(2)}%
                            </td>
                          </tr>
                        );
                      })}
                    </tbody>
                  </table>

                  {visibleTrades.length === 0 && (
                    <div className='py-8 text-center text-[var(--to-text-secondary)]'>
                      No trades yet. Run a backtest to see results.
                    </div>
                  )}
                </div>
              </Card>
            </TabsContent>

            <TabsContent value='performance' className='mt-4'>
              <BacktestPerformanceTab
                trades={visibleTrades}
                stats={
                  stats ?? {
                    total_trades: 0,
                    winning_trades: 0,
                    losing_trades: 0,
                    win_rate: 0,
                    total_return: 0,
                    sharpe_ratio: 0,
                    max_drawdown: 0,
                    profit_factor: 0,
                    avg_win: 0,
                    avg_loss: 0,
                    largest_win: 0,
                    largest_loss: 0,
                    avg_trade_duration: '0m',
                    exposure_time: 0,
                  }
                }
                initialCash={backtestResult.initial_cash}
                finalEquity={backtestResult.final_equity}
              />
            </TabsContent>
          </Tabs>
        </>
      )}

      {/* Error State */}
      {runBacktestMutation.isError && (
        <div className='rounded-lg border border-[var(--to-short)]/30 bg-[var(--to-short)]/10 px-3 py-2.5'>
          <div className='flex items-center gap-2'>
            <AlertCircle className='h-3.5 w-3.5 text-[var(--to-short)]' />
            <p className='text-xs text-[var(--to-short)]'>
              Backtest failed: {runBacktestMutation.error?.message}
            </p>
          </div>
        </div>
      )}
    </div>
  );
}
