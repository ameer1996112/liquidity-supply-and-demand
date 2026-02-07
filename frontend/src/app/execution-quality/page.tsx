'use client';

import { useState } from 'react';
import {
  useTCASummary,
  useSlippageBySymbol,
  useSlippageByHour,
  useLatencyBreakdown,
  useTCAAlerts,
} from '@/hooks/useExecutionQuality';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  LineChart,
  Line,
} from 'recharts';
import { Skeleton } from '@/components/ui/skeleton';
import { AlertTriangle, Clock, TrendingDown, DollarSign } from 'lucide-react';
import { cn } from '@/lib/utils';

const PERIODS = ['1d', '7d', '30d'] as const;

type Period = (typeof PERIODS)[number];

function periodToDays(period: Period): number {
  switch (period) {
    case '1d':
      return 1;
    case '7d':
      return 7;
    case '30d':
      return 30;
  }
}

export default function ExecutionQualityPage() {
  const [period, setPeriod] = useState<Period>('7d');
  const days = periodToDays(period);

  const { data: tcaSummary, isLoading: summaryLoading } = useTCASummary(days);
  const { data: slippageBySymbol, isLoading: symbolLoading } =
    useSlippageBySymbol(30); // Always 30 days for symbol analysis
  const { data: slippageByHour, isLoading: hourLoading } = useSlippageByHour(7);
  const { data: latencyBreakdown, isLoading: latencyLoading } =
    useLatencyBreakdown(7);
  const { data: tcaAlerts, isLoading: alertsLoading } = useTCAAlerts(7);

  const hasHighSlippage = tcaSummary && tcaSummary.avg_slippage_pips < -2.0;

  return (
    <div className="space-y-6 p-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-lg font-semibold text-zinc-100">
            Execution Quality
          </h1>
          <p className="text-xs text-zinc-500 mt-1">
            Transaction Cost Analysis & Execution Metrics
          </p>
        </div>

        {/* Period Selector */}
        <div className="flex items-center gap-1 bg-[#1e222d] border border-[#2a2e39] rounded-md p-1">
          {PERIODS.map((p) => (
            <button
              key={p}
              onClick={() => setPeriod(p)}
              className={cn(
                'font-mono text-[11px] px-2.5 py-1 rounded transition-colors',
                period === p
                  ? 'bg-[#2a2e39] text-zinc-200'
                  : 'text-zinc-500 hover:text-zinc-300',
              )}
            >
              {p}
            </button>
          ))}
        </div>
      </div>

      {/* Summary Cards */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        <Card className="bg-[#1e222d] border-[#2a2e39]">
          <CardHeader className="pb-2">
            <CardTitle className="text-xs text-zinc-500 flex items-center gap-1.5">
              <TrendingDown className="h-3.5 w-3.5" />
              Avg Slippage
            </CardTitle>
          </CardHeader>
          <CardContent>
            {summaryLoading ? (
              <Skeleton className="h-6 w-20" />
            ) : (
              <div>
                <div
                  className={cn(
                    'text-2xl font-bold',
                    hasHighSlippage ? 'text-red-500' : 'text-zinc-100',
                  )}
                >
                  {tcaSummary?.avg_slippage_pips.toFixed(2) ?? '0.00'} pips
                </div>
                <div className="text-xs text-zinc-500 mt-1">
                  ${tcaSummary?.total_slippage_cost_usd.toFixed(2) ?? '0.00'}{' '}
                  total cost
                </div>
              </div>
            )}
          </CardContent>
        </Card>

        <Card className="bg-[#1e222d] border-[#2a2e39]">
          <CardHeader className="pb-2">
            <CardTitle className="text-xs text-zinc-500 flex items-center gap-1.5">
              <DollarSign className="h-3.5 w-3.5" />
              Avg Spread Cost
            </CardTitle>
          </CardHeader>
          <CardContent>
            {summaryLoading ? (
              <Skeleton className="h-6 w-20" />
            ) : (
              <div>
                <div className="text-2xl font-bold text-zinc-100">
                  ${tcaSummary?.avg_spread_cost_usd.toFixed(2) ?? '0.00'}
                </div>
                <div className="text-xs text-zinc-500 mt-1">Per trade</div>
              </div>
            )}
          </CardContent>
        </Card>

        <Card className="bg-[#1e222d] border-[#2a2e39]">
          <CardHeader className="pb-2">
            <CardTitle className="text-xs text-zinc-500 flex items-center gap-1.5">
              <Clock className="h-3.5 w-3.5" />
              Avg Execution Time
            </CardTitle>
          </CardHeader>
          <CardContent>
            {summaryLoading ? (
              <Skeleton className="h-6 w-20" />
            ) : (
              <div>
                <div className="text-2xl font-bold text-zinc-100">
                  {tcaSummary?.avg_execution_time_ms.toFixed(0) ?? '0'}ms
                </div>
                <div className="text-xs text-zinc-500 mt-1">
                  Signal to fill
                </div>
              </div>
            )}
          </CardContent>
        </Card>

        <Card className="bg-[#1e222d] border-[#2a2e39]">
          <CardHeader className="pb-2">
            <CardTitle className="text-xs text-zinc-500 flex items-center gap-1.5">
              <AlertTriangle className="h-3.5 w-3.5" />
              Total Trades
            </CardTitle>
          </CardHeader>
          <CardContent>
            {summaryLoading ? (
              <Skeleton className="h-6 w-20" />
            ) : (
              <div>
                <div className="text-2xl font-bold text-zinc-100">
                  {tcaSummary?.total_trades ?? 0}
                </div>
                <div className="text-xs text-zinc-500 mt-1">
                  Last {days} days
                </div>
              </div>
            )}
          </CardContent>
        </Card>
      </div>

      {/* Slippage by Symbol Chart */}
      <Card className="bg-[#1e222d] border-[#2a2e39]">
        <CardHeader>
          <CardTitle className="text-sm font-medium text-zinc-100">
            Slippage by Symbol (Last 30 Days)
          </CardTitle>
        </CardHeader>
        <CardContent>
          {symbolLoading ? (
            <Skeleton className="h-[300px] w-full" />
          ) : (
            <ResponsiveContainer width="100%" height={300}>
              <BarChart data={slippageBySymbol}>
                <CartesianGrid strokeDasharray="3 3" stroke="#2a2e39" />
                <XAxis
                  dataKey="symbol"
                  stroke="#6b7280"
                  style={{ fontSize: 11 }}
                />
                <YAxis
                  label={{
                    value: 'Avg Slippage (pips)',
                    angle: -90,
                    position: 'insideLeft',
                    style: { fontSize: 11, fill: '#6b7280' },
                  }}
                  stroke="#6b7280"
                  style={{ fontSize: 11 }}
                />
                <Tooltip
                  contentStyle={{
                    backgroundColor: '#131722',
                    border: '1px solid #2a2e39',
                    borderRadius: '4px',
                    fontSize: 11,
                  }}
                />
                <Bar
                  dataKey="avg_slippage_pips"
                  fill="#26a69a"
                  radius={[4, 4, 0, 0]}
                />
              </BarChart>
            </ResponsiveContainer>
          )}
        </CardContent>
      </Card>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {/* Slippage by Hour */}
        <Card className="bg-[#1e222d] border-[#2a2e39]">
          <CardHeader>
            <CardTitle className="text-sm font-medium text-zinc-100">
              Slippage by Hour (UTC)
            </CardTitle>
          </CardHeader>
          <CardContent>
            {hourLoading ? (
              <Skeleton className="h-[250px] w-full" />
            ) : (
              <ResponsiveContainer width="100%" height={250}>
                <LineChart data={slippageByHour}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#2a2e39" />
                  <XAxis
                    dataKey="hour"
                    stroke="#6b7280"
                    style={{ fontSize: 11 }}
                  />
                  <YAxis
                    stroke="#6b7280"
                    style={{ fontSize: 11 }}
                    label={{
                      value: 'Slippage (pips)',
                      angle: -90,
                      position: 'insideLeft',
                      style: { fontSize: 11, fill: '#6b7280' },
                    }}
                  />
                  <Tooltip
                    contentStyle={{
                      backgroundColor: '#131722',
                      border: '1px solid #2a2e39',
                      borderRadius: '4px',
                      fontSize: 11,
                    }}
                  />
                  <Line
                    type="monotone"
                    dataKey="avg_slippage_pips"
                    stroke="#26a69a"
                    strokeWidth={2}
                    dot={{ fill: '#26a69a', r: 3 }}
                  />
                </LineChart>
              </ResponsiveContainer>
            )}
          </CardContent>
        </Card>

        {/* Latency Breakdown */}
        <Card className="bg-[#1e222d] border-[#2a2e39]">
          <CardHeader>
            <CardTitle className="text-sm font-medium text-zinc-100">
              Latency Breakdown (Last 7 Days)
            </CardTitle>
          </CardHeader>
          <CardContent>
            {latencyLoading ? (
              <Skeleton className="h-[250px] w-full" />
            ) : (
              <div className="space-y-4">
                <div className="flex justify-between items-center">
                  <span className="text-xs text-zinc-500">
                    Signal → Submit
                  </span>
                  <span className="text-sm font-mono text-zinc-100">
                    {latencyBreakdown?.avg_signal_to_submit_ms.toFixed(0) ?? 0}
                    ms
                  </span>
                </div>
                <div className="flex justify-between items-center">
                  <span className="text-xs text-zinc-500">Submit → Fill</span>
                  <span className="text-sm font-mono text-zinc-100">
                    {latencyBreakdown?.avg_submit_to_fill_ms.toFixed(0) ?? 0}ms
                  </span>
                </div>
                <div className="flex justify-between items-center">
                  <span className="text-xs text-zinc-500">Total</span>
                  <span className="text-sm font-mono text-zinc-100 font-bold">
                    {latencyBreakdown?.avg_total_execution_ms.toFixed(0) ?? 0}
                    ms
                  </span>
                </div>
                <div className="border-t border-[#2a2e39] pt-4 space-y-2">
                  <div className="flex justify-between items-center">
                    <span className="text-xs text-zinc-500">P95 Latency</span>
                    <span className="text-xs font-mono text-zinc-400">
                      {latencyBreakdown?.p95_latency_ms.toFixed(0) ?? 0}ms
                    </span>
                  </div>
                  <div className="flex justify-between items-center">
                    <span className="text-xs text-zinc-500">P99 Latency</span>
                    <span className="text-xs font-mono text-zinc-400">
                      {latencyBreakdown?.p99_latency_ms.toFixed(0) ?? 0}ms
                    </span>
                  </div>
                </div>
              </div>
            )}
          </CardContent>
        </Card>
      </div>

      {/* TCA Alerts */}
      <Card className="bg-[#1e222d] border-[#2a2e39]">
        <CardHeader>
          <CardTitle className="text-sm font-medium text-zinc-100">
            Recent TCA Alerts (Last 7 Days)
          </CardTitle>
        </CardHeader>
        <CardContent>
          {alertsLoading ? (
            <Skeleton className="h-[200px] w-full" />
          ) : tcaAlerts && tcaAlerts.length > 0 ? (
            <div className="space-y-2">
              {tcaAlerts.slice(0, 10).map((alert) => (
                <div
                  key={alert.id}
                  className="flex items-center justify-between p-2 bg-[#131722] rounded border border-[#2a2e39]"
                >
                  <div className="flex items-center gap-2">
                    <AlertTriangle className="h-4 w-4 text-yellow-500" />
                    <div>
                      <div className="text-xs text-zinc-300">
                        {alert.alert_type === 'high_slippage' &&
                          `High slippage: ${alert.slippage_pips?.toFixed(1)} pips`}
                        {alert.alert_type === 'high_latency' &&
                          `High latency: ${alert.total_execution_ms}ms`}
                      </div>
                      <div className="text-[10px] text-zinc-600 font-mono">
                        Signal #{alert.signal_id}
                      </div>
                    </div>
                  </div>
                  <div className="text-[10px] text-zinc-600 font-mono">
                    {new Date(alert.created_at).toLocaleString()}
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <div className="text-center py-8 text-zinc-500 text-sm">
              No TCA alerts in the last 7 days
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
