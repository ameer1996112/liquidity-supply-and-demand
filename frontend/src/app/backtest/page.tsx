"use client";

import { useState } from "react";
import { useQuery, useMutation } from "@tanstack/react-query";
import { BacktestChart, Trade, Zone } from "@/components/backtest/BacktestChart";
import { FXReplayController } from "@/components/backtest/FXReplayController";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import { Play, TrendingUp, TrendingDown, DollarSign, Target, AlertCircle } from "lucide-react";
import { CandlestickData, Time } from "lightweight-charts";
import { backtestAPI } from "@/lib/api";

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
  require_liquidity_sweep?: boolean;
  reject_compression_arrival?: boolean;
  require_structure_break?: boolean;
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
  const [backtestResult, setBacktestResult] = useState<BacktestResponse | null>(null);
  const [replayMode, setReplayMode] = useState(false); // Replay mode OFF by default

  // Backtest configuration (matches Pine Aggressive profile)
  const [config, setConfig] = useState<BacktestRequest>({
    symbol: "XAUUSD",
    start_date: "2026-01-01",
    end_date: "2026-02-12",
    timeframe: "5m",
    initial_cash: 10000,
    commission: 0.0002,
    risk_percent: 0.5,
    min_rr_ratio: 1.5, // ← Changed from 2.0 to match Pine Aggressive
    require_liquidity_sweep: true, // ← Changed from false (Pine always requires this)
    reject_compression_arrival: false, // ← Changed from true (let more trades through)
    require_structure_break: false,
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
        return trade.entry_time <= (typeof lastCandleTime === 'number' ? lastCandleTime : Number(lastCandleTime));
      }
      return true; // Show all trades when not in replay mode
    }) || [];

  const stats = backtestResult?.stats;

  return (
    <div className="container mx-auto p-6 space-y-6">
      {/* Header */}
      <div className="flex justify-between items-center">
        <div>
          <h1 className="text-3xl font-bold">Backtest Lab 🧪</h1>
          <p className="text-gray-400">TradingView-style backtest visualization with FX Replay</p>
        </div>
      </div>

      {/* Configuration Panel */}
      <Card className="p-6">
        <div className="flex justify-between items-center mb-4">
          <h2 className="text-xl font-semibold">Configuration</h2>
          <div className="flex gap-2">
            <Button
              variant={config.min_rr_ratio === 2.0 ? "default" : "outline"}
              size="sm"
              onClick={() =>
                setConfig({
                  ...config,
                  risk_percent: 0.5,
                  min_rr_ratio: 2.0,
                  require_liquidity_sweep: true,
                  reject_compression_arrival: true,
                  require_structure_break: false,
                })
              }
            >
              Balanced
            </Button>
            <Button
              variant={config.min_rr_ratio === 1.5 ? "default" : "outline"}
              size="sm"
              onClick={() =>
                setConfig({
                  ...config,
                  risk_percent: 0.5,
                  min_rr_ratio: 1.5,
                  require_liquidity_sweep: true,
                  reject_compression_arrival: false,
                  require_structure_break: false,
                })
              }
            >
              Aggressive
            </Button>
          </div>
        </div>
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          <div>
            <label className="block text-sm text-gray-400 mb-2">Symbol</label>
            <select
              value={config.symbol}
              onChange={(e) => setConfig({ ...config, symbol: e.target.value })}
              className="w-full px-3 py-2 bg-gray-900 border border-gray-700 rounded-md"
            >
              <optgroup label="Forex - Majors">
                <option value="EURUSD">EUR/USD - Euro vs US Dollar</option>
                <option value="GBPUSD">GBP/USD - British Pound vs US Dollar</option>
                <option value="USDJPY">USD/JPY - US Dollar vs Japanese Yen</option>
                <option value="USDCHF">USD/CHF - US Dollar vs Swiss Franc</option>
                <option value="AUDUSD">AUD/USD - Australian Dollar vs US Dollar</option>
                <option value="NZDUSD">NZD/USD - New Zealand Dollar vs US Dollar</option>
                <option value="USDCAD">USD/CAD - US Dollar vs Canadian Dollar</option>
              </optgroup>
              <optgroup label="Forex - Crosses">
                <option value="EURGBP">EUR/GBP - Euro vs British Pound</option>
                <option value="EURJPY">EUR/JPY - Euro vs Japanese Yen</option>
                <option value="GBPJPY">GBP/JPY - British Pound vs Japanese Yen</option>
                <option value="AUDJPY">AUD/JPY - Australian Dollar vs Japanese Yen</option>
              </optgroup>
              <optgroup label="Metals">
                <option value="XAUUSD">XAU/USD - Gold vs US Dollar</option>
                <option value="XAGUSD">XAG/USD - Silver vs US Dollar</option>
              </optgroup>
              <optgroup label="Indices">
                <option value="NAS100">NAS100 - NASDAQ 100</option>
                <option value="US30">US30 - Dow Jones 30</option>
                <option value="SPX500">SPX500 - S&P 500</option>
              </optgroup>
              <optgroup label="Crypto">
                <option value="BTCUSD">BTC/USD - Bitcoin vs US Dollar</option>
                <option value="ETHUSD">ETH/USD - Ethereum vs US Dollar</option>
              </optgroup>
            </select>
          </div>

          <div>
            <label className="block text-sm text-gray-400 mb-2">Start Date</label>
            <input
              type="date"
              value={config.start_date}
              onChange={(e) => setConfig({ ...config, start_date: e.target.value })}
              className="w-full px-3 py-2 bg-gray-900 border border-gray-700 rounded-md"
            />
          </div>

          <div>
            <label className="block text-sm text-gray-400 mb-2">End Date</label>
            <input
              type="date"
              value={config.end_date}
              onChange={(e) => setConfig({ ...config, end_date: e.target.value })}
              className="w-full px-3 py-2 bg-gray-900 border border-gray-700 rounded-md"
            />
          </div>

          <div>
            <label className="block text-sm text-gray-400 mb-2">Timeframe</label>
            <select
              value={config.timeframe}
              onChange={(e) => setConfig({ ...config, timeframe: e.target.value })}
              className="w-full px-3 py-2 bg-gray-900 border border-gray-700 rounded-md"
            >
              <option value="5m">5 Minutes</option>
              <option value="15m">15 Minutes</option>
              <option value="1h">1 Hour</option>
              <option value="4h">4 Hours</option>
              <option value="1d">1 Day</option>
            </select>
          </div>
        </div>

        {/* AI Guardian Filters */}
        <div className="mt-4 flex gap-4">
          <label className="flex items-center gap-2">
            <input
              type="checkbox"
              checked={config.require_liquidity_sweep}
              onChange={(e) => setConfig({ ...config, require_liquidity_sweep: e.target.checked })}
              className="rounded"
            />
            <span className="text-sm">Require Liquidity Sweep</span>
          </label>

          <label className="flex items-center gap-2">
            <input
              type="checkbox"
              checked={config.reject_compression_arrival}
              onChange={(e) => setConfig({ ...config, reject_compression_arrival: e.target.checked })}
              className="rounded"
            />
            <span className="text-sm">Reject Compression</span>
          </label>

          <label className="flex items-center gap-2">
            <input
              type="checkbox"
              checked={config.require_structure_break}
              onChange={(e) => setConfig({ ...config, require_structure_break: e.target.checked })}
              className="rounded"
            />
            <span className="text-sm">Require Structure Break</span>
          </label>
        </div>

        <Button
          onClick={handleRunBacktest}
          disabled={runBacktestMutation.isPending}
          className="mt-4"
          size="lg"
        >
          <Play className="h-4 w-4 mr-2" />
          {runBacktestMutation.isPending ? "Running Backtest..." : "Run Backtest"}
        </Button>
      </Card>

      {/* Results */}
      {backtestResult && (
        <>
          {/* Stats Cards */}
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            <Card className="p-4">
              <div className="flex items-center gap-2 mb-2">
                <Target className="h-4 w-4 text-blue-500" />
                <p className="text-sm text-gray-400">Total Trades</p>
              </div>
              <p className="text-2xl font-bold">{stats?.total_trades}</p>
            </Card>

            <Card className="p-4">
              <div className="flex items-center gap-2 mb-2">
                <TrendingUp className="h-4 w-4 text-green-500" />
                <p className="text-sm text-gray-400">Win Rate</p>
              </div>
              <p className="text-2xl font-bold text-green-500">{stats?.win_rate.toFixed(1)}%</p>
            </Card>

            <Card className="p-4">
              <div className="flex items-center gap-2 mb-2">
                <DollarSign className="h-4 w-4 text-yellow-500" />
                <p className="text-sm text-gray-400">Total Return</p>
              </div>
              <p
                className={`text-2xl font-bold ${
                  (stats?.total_return || 0) >= 0 ? "text-green-500" : "text-red-500"
                }`}
              >
                {stats?.total_return.toFixed(2)}%
              </p>
            </Card>

            <Card className="p-4">
              <div className="flex items-center gap-2 mb-2">
                <TrendingDown className="h-4 w-4 text-red-500" />
                <p className="text-sm text-gray-400">Max Drawdown</p>
              </div>
              <p className="text-2xl font-bold text-red-500">{stats?.max_drawdown.toFixed(2)}%</p>
            </Card>
          </div>

          {/* Chart */}
          <Card className="p-6">
            <div className="flex justify-between items-center mb-4">
              <h2 className="text-xl font-semibold">Backtest Chart</h2>
              <Button
                variant={replayMode ? "default" : "outline"}
                size="sm"
                onClick={() => {
                  setReplayMode(!replayMode);
                  if (!replayMode) {
                    setCurrentCandleIndex(0); // Reset to start when enabling replay
                  }
                }}
              >
                <Play className="h-4 w-4 mr-2" />
                {replayMode ? "Exit Replay Mode" : "Enable FX Replay"}
              </Button>
            </div>

            <BacktestChart candles={chartCandles} trades={visibleTrades} height={600} />

            {replayMode && (
              <div className="mt-4">
                <FXReplayController
                  candles={backtestResult.candles as unknown as CandlestickData<Time>[]}
                  currentIndex={currentCandleIndex}
                  onCandleIndexChange={setCurrentCandleIndex}
                />
              </div>
            )}
          </Card>

          {/* Trade List */}
          <Card className="p-6">
            <h2 className="text-xl font-semibold mb-4">Trade History</h2>
            <div className="space-y-2">
              {visibleTrades.map((trade, index) => (
                <div
                  key={index}
                  className="flex items-center justify-between p-4 bg-gray-900 rounded-lg border border-gray-800"
                >
                  <div className="flex items-center gap-4">
                    <Badge variant={trade.side === "long" ? "default" : "destructive"}>
                      {trade.side.toUpperCase()}
                    </Badge>
                    <div className="text-sm">
                      <p className="text-gray-400">Entry: {trade.entry_price.toFixed(5)}</p>
                      <p className="text-gray-400">Exit: {trade.exit_price.toFixed(5)}</p>
                    </div>
                  </div>

                  <div className={`text-lg font-bold ${trade.pnl >= 0 ? "text-green-500" : "text-red-500"}`}>
                    {trade.pnl >= 0 ? "+" : ""}${trade.pnl.toFixed(2)}
                  </div>
                </div>
              ))}
            </div>
          </Card>
        </>
      )}

      {/* Error State */}
      {runBacktestMutation.isError && (
        <Card className="p-6 bg-red-900/20 border-red-800">
          <div className="flex items-center gap-2">
            <AlertCircle className="h-5 w-5 text-red-500" />
            <p className="text-red-500">Backtest failed: {runBacktestMutation.error?.message}</p>
          </div>
        </Card>
      )}
    </div>
  );
}
