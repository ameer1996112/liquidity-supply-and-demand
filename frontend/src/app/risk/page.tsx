'use client';

import {
  useRiskMonitor,
  type AccountGuardCard,
  type GuardRailStatus,
  type RiskMonitorData,
} from '@/hooks/useRiskMonitor';
import { Skeleton } from '@/components/ui/skeleton';
import { cn } from '@/lib/utils';
import { ClientDate } from '@/components/ui/ClientDate';
import {
  Activity,
  AlertCircle,
  BookOpen,
  Gauge,
  Shield,
  ShieldCheck,
  TrendingDown,
} from 'lucide-react';
import { useConnectionHealth } from '@/hooks/useConnectionHealth';
import { PageStatusBanner } from '@/components/shared/PageStatusBanner';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { GuardsPanel } from '@/components/rules/GuardsPanel';
import { RiskRulesPanel } from '@/components/rules/RiskRulesPanel';
import { StrategyRulesPanel } from '@/components/rules/StrategyRulesPanel';

export default function RiskMonitorPage() {
  const { status } = useConnectionHealth();

  const tabClass =
    'flex items-center gap-1.5 rounded-md px-3 py-1.5 text-[11px] font-medium data-[state=active]:bg-indigo-600/20 data-[state=active]:text-indigo-300 data-[state=inactive]:text-[var(--to-text-dim)]';

  return (
    <div className='space-y-4 animate-fade-in-up'>
      <div className='flex items-center gap-3'>
        <div className='flex h-9 w-9 items-center justify-center rounded-lg bg-indigo-500/10 border border-indigo-500/20'>
          <Shield className='h-4 w-4 text-indigo-400' />
        </div>
        <div>
          <h1 className='page-title text-lg font-semibold'>Risk & Rules</h1>
          <p className='page-subtitle mt-0.5 text-[11px]'>
            Live risk monitoring, trade guards, and strategy rules
          </p>
        </div>
      </div>

      <PageStatusBanner status={status} surfaceLabel='Risk decisions' />

      <Tabs defaultValue='monitor'>
        <TabsList className='surface-soft rounded-lg border border-[var(--to-border)] p-0.5'>
          <TabsTrigger value='monitor' className={tabClass} style={{ fontFamily: 'var(--font-sans)' }}>
            <Gauge className='h-3.5 w-3.5' />
            Monitor
          </TabsTrigger>
          <TabsTrigger value='guards' className={tabClass} style={{ fontFamily: 'var(--font-sans)' }}>
            <Shield className='h-3.5 w-3.5' />
            Guards
          </TabsTrigger>
          <TabsTrigger value='risk-rules' className={tabClass} style={{ fontFamily: 'var(--font-sans)' }}>
            <ShieldCheck className='h-3.5 w-3.5' />
            Risk Rules
          </TabsTrigger>
          <TabsTrigger value='strategy' className={tabClass} style={{ fontFamily: 'var(--font-sans)' }}>
            <BookOpen className='h-3.5 w-3.5' />
            Strategy
          </TabsTrigger>
        </TabsList>

        <TabsContent value='monitor' className='mt-4'>
          <RiskMonitorTab />
        </TabsContent>

        <TabsContent value='guards' className='mt-4'>
          <GuardsPanel />
        </TabsContent>

        <TabsContent value='risk-rules' className='mt-4'>
          <RiskRulesPanel />
        </TabsContent>

        <TabsContent value='strategy' className='mt-4'>
          <StrategyRulesPanel />
        </TabsContent>
      </Tabs>
    </div>
  );
}

function RiskMonitorTab() {
  const { data, isLoading, error } = useRiskMonitor();

  if (isLoading || error) return <LoadingSkeleton />;
  if (!data) return null;

  return (
    <div className='space-y-3'>
      <SummaryStrip data={data} />
      <div className='grid grid-cols-1 gap-3 xl:grid-cols-2'>
        {data.accounts.map((account) => (
          <AccountCard key={account.account_name} account={account} />
        ))}
      </div>
      <div
        className='text-right text-[10px] text-[var(--to-text-dim)]'
        style={{ fontFamily: 'var(--font-mono)' }}
      >
        updated <ClientDate render={() => new Date(data.last_updated).toLocaleTimeString()} />
      </div>
    </div>
  );
}

function SummaryStrip({ data }: { data: RiskMonitorData }) {
  const cards = [
    { label: 'Total Accounts', value: String(data.summary.total_accounts) },
    { label: 'Total Equity', value: usd(data.summary.total_equity_usd) },
    {
      label: 'Daily PnL',
      value: signedUsd(data.summary.total_daily_pnl_usd),
      tone: data.summary.total_daily_pnl_usd < 0 ? 'text-[var(--to-short)]' : 'text-[var(--to-long)]',
    },
    { label: 'Open Positions', value: String(data.summary.total_open_positions) },
    { label: 'Warnings', value: String(data.summary.accounts_in_warning) },
    { label: 'Blocked', value: String(data.summary.accounts_blocked) },
  ];

  return (
    <div className='glow-card p-4'>
      <div className='mb-3 flex items-center gap-2'>
        <Activity className='h-3.5 w-3.5 text-[var(--to-accent-blue)]' />
        <span className='panel-label'>Fleet Summary</span>
      </div>
      <div className='grid grid-cols-2 gap-3 md:grid-cols-3 xl:grid-cols-6'>
        {cards.map((card) => (
          <div key={card.label} className='rounded-lg border border-[var(--to-border)] bg-[var(--to-panel)]/60 p-3'>
            <div className='text-[10px] text-[var(--to-text-dim)]' style={{ fontFamily: 'var(--font-sans)' }}>
              {card.label}
            </div>
            <div
              className={cn('mt-1 text-sm font-semibold tabular-nums text-[var(--to-text-primary)]', card.tone)}
              style={{ fontFamily: 'var(--font-mono)' }}
            >
              {card.value}
            </div>
          </div>
        ))}
      </div>
      {data.summary.global_kill_switch_active && (
        <div className='mt-3 flex items-center gap-2 rounded-lg border border-[var(--to-short)]/30 bg-[var(--to-short)]/10 p-2 text-[11px] text-[var(--to-short)]'>
          <AlertCircle className='h-3.5 w-3.5' />
          Global kill switch is active.
        </div>
      )}
    </div>
  );
}

function AccountCard({ account }: { account: AccountGuardCard }) {
  return (
    <div className='glow-card p-4'>
      <div className='flex items-start justify-between gap-3 border-b border-[var(--to-border)] pb-3'>
        <div>
          <div className='text-sm font-semibold text-[var(--to-text-primary)]'>{account.account_name}</div>
          <div className='mt-1 flex flex-wrap items-center gap-2 text-[10px] text-[var(--to-text-dim)]'>
            <span>{account.account_type}</span>
            {account.evaluation_phase && <span>{account.evaluation_phase}</span>}
            {account.prop_firm_name && <span>{account.prop_firm_name}</span>}
            <span>{account.run_mode}</span>
            {account.connection_status && <span>{account.connection_status}</span>}
          </div>
        </div>
        <div
          className={cn(
            'rounded-full border px-2 py-1 text-[10px] uppercase tracking-[0.14em]',
            account.blocked
              ? 'border-[var(--to-short)]/40 bg-[var(--to-short)]/10 text-[var(--to-short)]'
              : account.warning_message
              ? 'border-[var(--to-warning)]/40 bg-[var(--to-warning)]/10 text-[var(--to-warning)]'
              : 'border-[var(--to-long)]/30 bg-[var(--to-long)]/10 text-[var(--to-long)]'
          )}
          style={{ fontFamily: 'var(--font-mono)' }}
        >
          {account.blocked ? 'Blocked' : account.warning_message ? 'Warning' : 'Healthy'}
        </div>
      </div>

      <div className='mt-3 grid grid-cols-2 gap-3 md:grid-cols-4'>
        <Metric label='Starting' value={usd(account.starting_balance_usd)} />
        <Metric label='Equity' value={usd(account.current_equity_usd)} />
        <Metric
          label='Daily PnL'
          value={signedUsd(account.daily_pnl_usd)}
          tone={account.daily_pnl_usd < 0 ? 'text-[var(--to-short)]' : 'text-[var(--to-long)]'}
        />
        <Metric label='Risk %' value={`${account.effective_risk_pct.toFixed(2)}%`} />
      </div>

      <div className='mt-3 grid grid-cols-1 gap-3 md:grid-cols-2'>
        <ProgressBlock
          title='Drawdown'
          current={`${account.current_drawdown_pct.toFixed(2)}% / ${account.max_drawdown_allowed_pct.toFixed(1)}%`}
          percent={account.drawdown_utilization_pct}
        />
        <ProgressBlock
          title='Daily Loss Used'
          current={`${usd(account.daily_loss_used_usd)} / ${usd(account.daily_loss_limit_usd)}`}
          percent={account.daily_loss_limit_usd > 0 ? (account.daily_loss_used_usd / account.daily_loss_limit_usd) * 100 : 0}
        />
      </div>

      <div className='mt-3 grid grid-cols-2 gap-3 md:grid-cols-4'>
        <Metric label='Open Pos' value={`${account.open_positions} / ${account.max_positions}`} />
        <Metric label='Trades Today' value={`${account.trades_today} / ${account.max_trades_today}`} />
        <Metric label='Risk Mult' value={`${account.risk_multiplier.toFixed(2)}x`} />
        <Metric label='Base Risk' value={`${account.base_risk_pct.toFixed(2)}%`} />
      </div>

      {(account.warning_message || account.blocked_reason) && (
        <div className='mt-3 rounded-lg border border-[var(--to-warning)]/30 bg-[var(--to-warning)]/10 p-2 text-[11px] text-[var(--to-warning)]'>
          {account.blocked_reason || account.warning_message}
        </div>
      )}

      <div className='mt-3 space-y-2 border-t border-[var(--to-border)] pt-3'>
        <div className='text-[10px] uppercase tracking-[0.16em] text-[var(--to-text-dim)]' style={{ fontFamily: 'var(--font-mono)' }}>
          Guard Rails
        </div>
        <div className='space-y-2'>
          {account.guard_rails.map((rail) => (
            <GuardRailRow key={`${account.account_name}-${rail.name}`} rail={rail} />
          ))}
        </div>
      </div>
    </div>
  );
}

function Metric({
  label,
  value,
  tone,
}: {
  label: string;
  value: string;
  tone?: string;
}) {
  return (
    <div className='rounded-lg border border-[var(--to-border)] bg-[var(--to-panel)]/60 p-3'>
      <div className='text-[10px] text-[var(--to-text-dim)]'>{label}</div>
      <div className={cn('mt-1 text-sm font-semibold tabular-nums text-[var(--to-text-primary)]', tone)} style={{ fontFamily: 'var(--font-mono)' }}>
        {value}
      </div>
    </div>
  );
}

function ProgressBlock({
  title,
  current,
  percent,
}: {
  title: string;
  current: string;
  percent: number;
}) {
  const color =
    percent >= 80 ? 'bg-[var(--to-short)]' : percent >= 50 ? 'bg-[var(--to-warning)]' : 'bg-[var(--to-long)]';
  return (
    <div className='rounded-lg border border-[var(--to-border)] bg-[var(--to-panel)]/60 p-3'>
      <div className='mb-1 flex items-baseline justify-between gap-2'>
        <span className='text-[10px] text-[var(--to-text-dim)]'>{title}</span>
        <span className='text-[11px] tabular-nums text-[var(--to-text-primary)]' style={{ fontFamily: 'var(--font-mono)' }}>
          {current}
        </span>
      </div>
      <div className='h-1.5 overflow-hidden rounded-full bg-[var(--to-border)]'>
        <div className={cn('h-full transition-all', color)} style={{ width: `${Math.min(percent, 100)}%` }} />
      </div>
      <div className='mt-1 text-[9px] text-[var(--to-text-dim)]' style={{ fontFamily: 'var(--font-mono)' }}>
        {percent.toFixed(0)}% utilization
      </div>
    </div>
  );
}

function GuardRailRow({ rail }: { rail: GuardRailStatus }) {
  const tone =
    rail.severity === 'critical'
      ? 'text-[var(--to-short)] border-[var(--to-short)]/30 bg-[var(--to-short)]/10'
      : rail.severity === 'warning'
      ? 'text-[var(--to-warning)] border-[var(--to-warning)]/30 bg-[var(--to-warning)]/10'
      : 'text-[var(--to-text-secondary)] border-[var(--to-border)] bg-[var(--to-panel)]/50';

  return (
    <div className={cn('rounded-lg border p-2', tone)}>
      <div className='flex items-center justify-between gap-2'>
        <span className='text-[11px] font-medium'>{rail.name}</span>
        <span className='text-[10px] uppercase tracking-[0.14em]' style={{ fontFamily: 'var(--font-mono)' }}>
          {rail.status}
        </span>
      </div>
      <div className='mt-1 text-[10px] opacity-90'>{rail.message}</div>
    </div>
  );
}

function usd(value: number) {
  return `$${value.toFixed(2)}`;
}

function signedUsd(value: number) {
  return `${value >= 0 ? '+' : '-'}$${Math.abs(value).toFixed(2)}`;
}

function LoadingSkeleton() {
  return (
    <div className='space-y-3'>
      <Skeleton className='h-32 w-full rounded-xl' />
      <div className='grid grid-cols-1 gap-3 xl:grid-cols-2'>
        <Skeleton className='h-72 w-full rounded-xl' />
        <Skeleton className='h-72 w-full rounded-xl' />
      </div>
    </div>
  );
}
