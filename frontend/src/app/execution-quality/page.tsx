'use client';

import { useState } from 'react';
import {
  useTCASummary,
  useSlippageBySymbol,
  useSlippageByHour,
  useLatencyBreakdown,
  useTCAAlerts,
} from '@/hooks/useExecutionQuality';
import { usePipelineTraces, useTraceAccounts } from '@/hooks/usePipelineTraces';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
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
import {
  AlertTriangle,
  Clock,
  TrendingDown,
  DollarSign,
  Activity,
  RefreshCw,
} from 'lucide-react';
import { cn } from '@/lib/utils';
import { ClientDate } from '@/components/ui/ClientDate';
import { TraceTable } from '@/components/execution/TraceTable';

// ── Period selector ───────────────────────────────────────────────────────────

const PERIODS = ['1d', '7d', '30d'] as const;
type Period = (typeof PERIODS)[number];

function periodToDays(period: Period): number {
  switch (period) {
    case '1d': return 1;
    case '7d': return 7;
    case '30d': return 30;
  }
}

// ── Account switcher ──────────────────────────────────────────────────────────

interface AccountSwitcherProps {
  accounts: { account_id: string; name: string }[];
  selected: string | null;
  onChange: (id: string | null) => void;
}

function AccountSwitcher({ accounts, selected, onChange }: AccountSwitcherProps) {
  // Hide when only the "default" account exists — single-account deployments
  const hasMultiple = accounts.length > 1 || (accounts.length === 1 && accounts[0].account_id !== 'default');
  if (!hasMultiple) return null;

  return (
    <div className='flex items-center gap-1.5'>
      <span className='text-[10px] uppercase tracking-widest text-slate-600'>Account</span>
      <div className='flex items-center gap-0.5 rounded border border-[var(--to-border)] bg-[var(--to-surface)] p-0.5'>
        <button
          onClick={() => onChange(null)}
          className={cn(
            'rounded px-2.5 py-1 font-mono text-[10px] transition-colors',
            selected === null
              ? 'bg-slate-700 text-slate-100'
              : 'text-slate-500 hover:text-slate-300',
          )}
        >
          All
        </button>
        {accounts.map((acc) => (
          <button
            key={acc.account_id}
            onClick={() => onChange(acc.account_id)}
            className={cn(
              'rounded px-2.5 py-1 font-mono text-[10px] transition-colors',
              selected === acc.account_id
                ? 'bg-[var(--to-accent-blue)]/20 text-blue-300'
                : 'text-slate-500 hover:text-slate-300',
            )}
          >
            {acc.account_id}
          </button>
        ))}
      </div>
    </div>
  );
}

// ── Page ──────────────────────────────────────────────────────────────────────

export default function ExecutionQualityPage() {
  const [period, setPeriod] = useState<Period>('7d');
  const [activeTab, setActiveTab] = useState<'tca' | 'traces'>('traces');
  const [selectedAccount, setSelectedAccount] = useState<string | null>(null);
  const days = periodToDays(period);

  // TCA data
  const { data: tcaSummary, isLoading: summaryLoading } = useTCASummary(days);
  const { data: slippageBySymbol, isLoading: symbolLoading } = useSlippageBySymbol(30);
  const { data: slippageByHour, isLoading: hourLoading } = useSlippageByHour(7);
  const { data: latencyBreakdown, isLoading: latencyLoading } = useLatencyBreakdown(7);
  const { data: tcaAlerts, isLoading: alertsLoading } = useTCAAlerts(7);

  // Traces data
  const { data: traces, isLoading: tracesLoading, error: tracesError, refetch } = usePipelineTraces({
    limit: 50,
    account_id: selectedAccount ?? undefined,
  });
  const { data: accounts = [] } = useTraceAccounts();

  const hasHighSlippage = tcaSummary && tcaSummary.avg_slippage_pips < -2.0;

  return (
    <div className='space-y-4'>
      {/* ── Page header ─────────────────────────────────────────────── */}
      <div className='flex items-center justify-between'>
        <div>
          <h1 className='page-title text-lg font-semibold'>Execution Quality</h1>
          <p className='page-subtitle mt-0.5 text-xs'>
            Pipeline traces · TCA metrics · latency instrumentation
          </p>
        </div>

        <div className='flex items-center gap-3'>
          {/* Account switcher — only shown when multiple accounts exist */}
          <AccountSwitcher
            accounts={accounts}
            selected={selectedAccount}
            onChange={setSelectedAccount}
          />

          {/* Period selector (TCA only) */}
          {activeTab === 'tca' && (
            <div className='flex items-center gap-1 rounded border border-[var(--to-border)] bg-[var(--to-surface)] p-0.5'>
              {PERIODS.map((p) => (
                <button
                  key={p}
                  onClick={() => setPeriod(p)}
                  className={cn(
                    'rounded px-2.5 py-1 font-mono text-[11px] transition-colors',
                    period === p
                      ? 'bg-indigo-600/20 text-indigo-300'
                      : 'text-slate-500 hover:text-slate-300',
                  )}
                >
                  {p}
                </button>
              ))}
            </div>
          )}

          {/* Refresh for traces */}
          {activeTab === 'traces' && (
            <button
              onClick={() => refetch()}
              className='flex items-center gap-1.5 rounded border border-[var(--to-border)] bg-[var(--to-surface)] px-2.5 py-1.5 text-[11px] text-slate-400 transition-colors hover:text-slate-200'
            >
              <RefreshCw className='h-3 w-3' />
              Refresh
            </button>
          )}
        </div>
      </div>

      {/* ── Tabs ────────────────────────────────────────────────────── */}
      <Tabs value={activeTab} onValueChange={(v) => setActiveTab(v as 'tca' | 'traces')}>
        <TabsList className='h-8 border border-[var(--to-border)] bg-[var(--to-surface)] p-0.5'>
          <TabsTrigger
            value='traces'
            className='h-7 px-3 text-[11px] data-[state=active]:bg-[var(--to-surface-raised)] data-[state=active]:text-slate-100'
          >
            <Activity className='mr-1.5 h-3 w-3' />
            Pipeline Traces
          </TabsTrigger>
          <TabsTrigger
            value='tca'
            className='h-7 px-3 text-[11px] data-[state=active]:bg-[var(--to-surface-raised)] data-[state=active]:text-slate-100'
          >
            <TrendingDown className='mr-1.5 h-3 w-3' />
            TCA Metrics
          </TabsTrigger>
        </TabsList>

        {/* ══════════════════════════════════════════════════════════
            TAB 1 — Pipeline Traces
        ══════════════════════════════════════════════════════════ */}
        <TabsContent value='traces' className='mt-4 space-y-4'>
          {/* Stats row */}
          <div className='grid grid-cols-2 gap-3 sm:grid-cols-4'>
            <StatPill
              label='Total Traces'
              value={traces ? String(traces.length) : '—'}
              loading={tracesLoading}
            />
            <StatPill
              label='Errors'
              value={
                traces
                  ? String(traces.filter((t) => !!t.error_type).length)
                  : '—'
              }
              loading={tracesLoading}
              valueClass='text-red-400'
            />
            <StatPill
              label='Avg Latency'
              value={
                traces && traces.length
                  ? (() => {
                      const vals = traces
                        .map((t) => t.total_ms)
                        .filter((v): v is number => v != null);
                      if (!vals.length) return '—';
                      const avg = vals.reduce((a, b) => a + b, 0) / vals.length;
                      return avg < 1000 ? `${Math.round(avg)} ms` : `${(avg / 1000).toFixed(2)} s`;
                    })()
                  : '—'
              }
              loading={tracesLoading}
            />
            <StatPill
              label='p95 Latency'
              value={
                traces && traces.length
                  ? (() => {
                      const vals = traces
                        .map((t) => t.total_ms)
                        .filter((v): v is number => v != null)
                        .sort((a, b) => a - b);
                      if (!vals.length) return '—';
                      const idx = Math.floor(vals.length * 0.95);
                      const p95 = vals[Math.min(idx, vals.length - 1)];
                      return p95 < 1000 ? `${Math.round(p95)} ms` : `${(p95 / 1000).toFixed(2)} s`;
                    })()
                  : '—'
              }
              loading={tracesLoading}
            />
          </div>

          {/* The table */}
          <TraceTable
            traces={traces}
            isLoading={tracesLoading}
            error={tracesError}
          />

          <p className='text-[10px] text-slate-700'>
            Showing last 50 pipeline traces
            {selectedAccount ? ` for account "${selectedAccount}"` : ' across all accounts'}.
            Click a row to inspect hop timestamps and broker status.
          </p>
        </TabsContent>

        {/* ══════════════════════════════════════════════════════════
            TAB 2 — TCA Metrics (existing content, unchanged)
        ══════════════════════════════════════════════════════════ */}
        <TabsContent value='tca' className='mt-4 space-y-4'>
          {/* Summary Cards */}
          <div className='grid grid-cols-1 gap-4 md:grid-cols-4'>
            <Card className='tv-card'>
              <CardHeader className='pb-2'>
                <CardTitle className='flex items-center gap-1.5 text-xs text-slate-500'>
                  <TrendingDown className='h-3.5 w-3.5' />
                  Avg Slippage
                </CardTitle>
              </CardHeader>
              <CardContent>
                {summaryLoading ? (
                  <Skeleton className='h-6 w-20 bg-slate-800/60' />
                ) : (
                  <div>
                    <div
                      className={cn(
                        'text-2xl font-bold',
                        hasHighSlippage ? 'text-red-400' : 'text-slate-100',
                      )}
                    >
                      {tcaSummary?.avg_slippage_pips?.toFixed(2) ?? '0.00'} pips
                    </div>
                    <div className='mt-1 text-xs text-slate-500'>
                      ${tcaSummary?.total_slippage_cost_usd?.toFixed(2) ?? '0.00'} total cost
                    </div>
                  </div>
                )}
              </CardContent>
            </Card>

            <Card className='tv-card'>
              <CardHeader className='pb-2'>
                <CardTitle className='flex items-center gap-1.5 text-xs text-slate-500'>
                  <DollarSign className='h-3.5 w-3.5' />
                  Avg Spread Cost
                </CardTitle>
              </CardHeader>
              <CardContent>
                {summaryLoading ? (
                  <Skeleton className='h-6 w-20 bg-slate-800/60' />
                ) : (
                  <div>
                    <div className='text-2xl font-bold text-slate-100'>
                      ${tcaSummary?.avg_spread_cost_usd?.toFixed(2) ?? '0.00'}
                    </div>
                    <div className='mt-1 text-xs text-slate-500'>Per trade</div>
                  </div>
                )}
              </CardContent>
            </Card>

            <Card className='tv-card'>
              <CardHeader className='pb-2'>
                <CardTitle className='flex items-center gap-1.5 text-xs text-slate-500'>
                  <Clock className='h-3.5 w-3.5' />
                  Avg Execution Time
                </CardTitle>
              </CardHeader>
              <CardContent>
                {summaryLoading ? (
                  <Skeleton className='h-6 w-20 bg-slate-800/60' />
                ) : (
                  <div>
                    <div className='text-2xl font-bold text-slate-100'>
                      {tcaSummary?.avg_execution_time_ms?.toFixed(0) ?? '0'}ms
                    </div>
                    <div className='mt-1 text-xs text-slate-500'>Signal to fill</div>
                  </div>
                )}
              </CardContent>
            </Card>

            <Card className='tv-card'>
              <CardHeader className='pb-2'>
                <CardTitle className='flex items-center gap-1.5 text-xs text-slate-500'>
                  <AlertTriangle className='h-3.5 w-3.5' />
                  Total Trades
                </CardTitle>
              </CardHeader>
              <CardContent>
                {summaryLoading ? (
                  <Skeleton className='h-6 w-20 bg-slate-800/60' />
                ) : (
                  <div>
                    <div className='text-2xl font-bold text-slate-100'>
                      {tcaSummary?.total_trades ?? 0}
                    </div>
                    <div className='mt-1 text-xs text-slate-500'>Last {days} days</div>
                  </div>
                )}
              </CardContent>
            </Card>
          </div>

          {/* Slippage by Symbol */}
          <Card className='tv-card'>
            <CardHeader>
              <CardTitle className='text-sm font-medium text-slate-100'>
                Slippage by Symbol (Last 30 Days)
              </CardTitle>
            </CardHeader>
            <CardContent>
              {symbolLoading ? (
                <Skeleton className='h-[300px] w-full bg-slate-800/60' />
              ) : (
                <ResponsiveContainer width='100%' height={300}>
                  <BarChart data={slippageBySymbol}>
                    <CartesianGrid strokeDasharray='3 3' stroke='#334155' />
                    <XAxis dataKey='symbol' stroke='#64748b' style={{ fontSize: 11 }} />
                    <YAxis
                      label={{
                        value: 'Avg Slippage (pips)',
                        angle: -90,
                        position: 'insideLeft',
                        style: { fontSize: 11, fill: '#64748b' },
                      }}
                      stroke='#64748b'
                      style={{ fontSize: 11 }}
                    />
                    <Tooltip
                      contentStyle={{
                        backgroundColor: '#0f172a',
                        border: '1px solid #334155',
                        borderRadius: '4px',
                        fontSize: 11,
                      }}
                    />
                    <Bar dataKey='avg_slippage_pips' fill='#10b981' radius={[4, 4, 0, 0]} />
                  </BarChart>
                </ResponsiveContainer>
              )}
            </CardContent>
          </Card>

          <div className='grid grid-cols-1 gap-4 md:grid-cols-2'>
            {/* Slippage by Hour */}
            <Card className='tv-card'>
              <CardHeader>
                <CardTitle className='text-sm font-medium text-slate-100'>
                  Slippage by Hour (UTC)
                </CardTitle>
              </CardHeader>
              <CardContent>
                {hourLoading ? (
                  <Skeleton className='h-[250px] w-full bg-slate-800/60' />
                ) : (
                  <ResponsiveContainer width='100%' height={250}>
                    <LineChart data={slippageByHour}>
                      <CartesianGrid strokeDasharray='3 3' stroke='#334155' />
                      <XAxis dataKey='hour' stroke='#64748b' style={{ fontSize: 11 }} />
                      <YAxis
                        stroke='#64748b'
                        style={{ fontSize: 11 }}
                        label={{
                          value: 'Slippage (pips)',
                          angle: -90,
                          position: 'insideLeft',
                          style: { fontSize: 11, fill: '#64748b' },
                        }}
                      />
                      <Tooltip
                        contentStyle={{
                          backgroundColor: '#0f172a',
                          border: '1px solid #334155',
                          borderRadius: '4px',
                          fontSize: 11,
                        }}
                      />
                      <Line
                        type='monotone'
                        dataKey='avg_slippage_pips'
                        stroke='#10b981'
                        strokeWidth={2}
                        dot={{ fill: '#10b981', r: 3 }}
                      />
                    </LineChart>
                  </ResponsiveContainer>
                )}
              </CardContent>
            </Card>

            {/* Latency Breakdown */}
            <Card className='tv-card'>
              <CardHeader>
                <CardTitle className='text-sm font-medium text-slate-100'>
                  Latency Breakdown (Last 7 Days)
                </CardTitle>
              </CardHeader>
              <CardContent>
                {latencyLoading ? (
                  <Skeleton className='h-[250px] w-full bg-slate-800/60' />
                ) : (
                  <div className='space-y-4'>
                    <LatRow label='Signal → Submit' ms={latencyBreakdown?.avg_signal_to_submit_ms} />
                    <LatRow label='Submit → Fill' ms={latencyBreakdown?.avg_submit_to_fill_ms} />
                    <LatRow label='Total' ms={latencyBreakdown?.avg_total_execution_ms} bold />
                    <div className='space-y-2 border-t border-slate-700 pt-4'>
                      <LatRow label='P95 Latency' ms={latencyBreakdown?.p95_latency_ms} small />
                      <LatRow label='P99 Latency' ms={latencyBreakdown?.p99_latency_ms} small />
                    </div>
                  </div>
                )}
              </CardContent>
            </Card>
          </div>

          {/* TCA Alerts */}
          <Card className='tv-card'>
            <CardHeader>
              <CardTitle className='text-sm font-medium text-slate-100'>
                Recent TCA Alerts (Last 7 Days)
              </CardTitle>
            </CardHeader>
            <CardContent>
              {alertsLoading ? (
                <Skeleton className='h-[200px] w-full bg-slate-800/60' />
              ) : tcaAlerts && tcaAlerts.length > 0 ? (
                <div className='space-y-2'>
                  {tcaAlerts.slice(0, 10).map((alert) => (
                    <div
                      key={alert.id}
                      className='flex items-center justify-between rounded border border-slate-700 bg-slate-900 p-2'
                    >
                      <div className='flex items-center gap-2'>
                        <AlertTriangle className='h-4 w-4 text-amber-400' />
                        <div>
                          <div className='text-xs text-slate-300'>
                            {alert.alert_type === 'high_slippage' &&
                              `High slippage: ${alert.slippage_pips?.toFixed(1)} pips`}
                            {alert.alert_type === 'high_latency' &&
                              `High latency: ${alert.total_execution_ms}ms`}
                          </div>
                          <div className='font-mono text-[10px] text-slate-500'>
                            Signal #{alert.signal_id}
                          </div>
                        </div>
                      </div>
                      <ClientDate
                        className='font-mono text-[10px] text-slate-500'
                        render={() => new Date(alert.created_at).toLocaleString()}
                      />
                    </div>
                  ))}
                </div>
              ) : (
                <div className='py-8 text-center text-sm text-slate-500'>
                  No TCA alerts in the last 7 days
                </div>
              )}
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>
    </div>
  );
}

// ── Small shared primitives ───────────────────────────────────────────────────

function StatPill({
  label,
  value,
  loading,
  valueClass,
}: {
  label: string;
  value: string;
  loading: boolean;
  valueClass?: string;
}) {
  return (
    <div className='rounded border border-[var(--to-border)] bg-[var(--to-surface)] px-3 py-2.5'>
      <div className='text-[10px] uppercase tracking-widest text-slate-600'>{label}</div>
      {loading ? (
        <Skeleton className='mt-1 h-5 w-14 bg-slate-800/60' />
      ) : (
        <div className={cn('mt-0.5 font-mono text-[15px] font-bold text-slate-100', valueClass)}>
          {value}
        </div>
      )}
    </div>
  );
}

function LatRow({
  label,
  ms,
  bold,
  small,
}: {
  label: string;
  ms?: number;
  bold?: boolean;
  small?: boolean;
}) {
  return (
    <div className='flex items-center justify-between'>
      <span className={cn('text-slate-500', small ? 'text-xs' : 'text-xs')}>{label}</span>
      <span
        className={cn(
          'font-mono tabular-nums text-slate-100',
          small ? 'text-xs text-slate-400' : 'text-sm',
          bold && 'font-bold',
        )}
      >
        {(ms ?? 0).toFixed(0)}ms
      </span>
    </div>
  );
}
