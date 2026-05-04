'use client';

import { AlertTriangle, Ban, CheckCircle2, Clock3, ShieldCheck } from 'lucide-react';
import { cn } from '@/lib/utils';
import type { TradeDecision, TradePermissionsDashboard } from '@/hooks/useTradePermissionsDashboard';

interface TradePermissionsPanelProps {
  data?: TradePermissionsDashboard;
  isLoading?: boolean;
}

const DECISION_STYLE: Record<TradeDecision, { label: string; className: string; Icon: typeof ShieldCheck }> = {
  TRADE_NORMAL_RISK: {
    label: 'Normal risk',
    className: 'border-[#0ecb81]/30 bg-[#0ecb81]/10 text-[#0ecb81]',
    Icon: ShieldCheck,
  },
  TRADE_REDUCED_RISK: {
    label: 'Reduced risk',
    className: 'border-[#f0b90b]/30 bg-[#f0b90b]/10 text-[#f0b90b]',
    Icon: AlertTriangle,
  },
  WATCH_ONLY: {
    label: 'Watch only',
    className: 'border-sky-400/30 bg-sky-400/10 text-sky-300',
    Icon: Clock3,
  },
  NO_TRADE: {
    label: 'No trade',
    className: 'border-[#f6465d]/30 bg-[#f6465d]/10 text-[#f6465d]',
    Icon: Ban,
  },
};

function CountTile({ label, value }: { label: string; value: number }) {
  return (
    <div className='rounded-md border border-[var(--to-border)] bg-[var(--to-surface-raised)] px-3 py-2'>
      <p className='text-[9px] font-semibold uppercase tracking-[0.12em] text-[var(--to-text-dim)]'>{label}</p>
      <p className='mt-1 font-mono text-lg font-bold leading-none text-[var(--to-text-primary)]'>{value}</p>
    </div>
  );
}

function SymbolReasons({ title, rows }: { title: string; rows: Record<string, string[]> }) {
  const entries = Object.entries(rows).slice(0, 4);
  if (entries.length === 0) return null;

  return (
    <div className='min-w-0'>
      <p className='mb-1 text-[10px] font-semibold uppercase tracking-[0.12em] text-[var(--to-text-dim)]'>{title}</p>
      <div className='space-y-1'>
        {entries.map(([symbol, reasons]) => (
          <div key={symbol} className='flex min-w-0 items-start gap-2 text-xs'>
            <span className='font-mono font-semibold text-[var(--to-text-primary)]'>{symbol}</span>
            <span className='min-w-0 truncate text-[var(--to-text-secondary)]'>{reasons.join(', ')}</span>
          </div>
        ))}
      </div>
    </div>
  );
}

export function TradePermissionsPanel({ data, isLoading }: TradePermissionsPanelProps) {
  const decision = data?.global_decision ?? 'NO_TRADE';
  const style = DECISION_STYLE[decision];
  const Icon = style.Icon;
  const allowed = data?.allowed_today ?? {};
  const blocked = data?.blocked_today ?? {};
  const watchOnly = data?.watch_only ?? {};
  const researchApprovedCount = Object.keys(data?.research_approved_candidates ?? {}).length;

  return (
    <section className='glow-card overflow-hidden'>
      <div className='to-panel-header'>
        <div className='flex items-center gap-2'>
          <span className='panel-label'>Trade Permissions</span>
          <span className='rounded-full border border-[var(--to-border)] bg-[var(--to-surface-raised)] px-2 py-0.5 font-mono text-[9px] text-[var(--to-text-dim)]'>
            DEV-266
          </span>
        </div>
        <div className={cn('flex items-center gap-1.5 rounded-md border px-2 py-1 text-[11px] font-semibold', style.className)}>
          <Icon className='h-3.5 w-3.5' />
          {style.label}
        </div>
      </div>

      <div className='grid gap-3 p-3 lg:grid-cols-[minmax(0,0.8fr)_minmax(0,1.2fr)]'>
        <div className='grid grid-cols-2 gap-2 sm:grid-cols-4 lg:grid-cols-2'>
          <CountTile label='Allowed' value={Object.keys(allowed).length} />
          <CountTile label='Blocked' value={Object.keys(blocked).length} />
          <CountTile label='Watch' value={Object.keys(watchOnly).length} />
          <CountTile label='Research' value={researchApprovedCount} />
        </div>

        <div className='grid gap-3 md:grid-cols-2'>
          {isLoading ? (
            <div className='rounded-md border border-[var(--to-border)] bg-[var(--to-surface-raised)] p-3 text-xs text-[var(--to-text-dim)]'>
              Loading permission state...
            </div>
          ) : Object.keys(allowed).length > 0 ? (
            <div className='min-w-0'>
              <p className='mb-1 text-[10px] font-semibold uppercase tracking-[0.12em] text-[var(--to-text-dim)]'>Allowed Today</p>
              <div className='space-y-1'>
                {Object.entries(allowed).slice(0, 4).map(([symbol, permission]) => (
                  <div key={symbol} className='flex min-w-0 items-center justify-between gap-2 text-xs'>
                    <span className='font-mono font-semibold text-[var(--to-text-primary)]'>{symbol}</span>
                    <span className='truncate text-[var(--to-text-secondary)]'>
                      {permission.status.replace('TRADE_', '').replaceAll('_', ' ')} · {permission.risk_per_trade_pct}%
                    </span>
                  </div>
                ))}
              </div>
            </div>
          ) : (
            <div className='rounded-md border border-[#f6465d]/20 bg-[#f6465d]/5 p-3 text-xs text-[var(--to-text-secondary)]'>
              No symbols are explicitly allowed today. This is a valid safe state.
            </div>
          )}

          <div className='grid gap-3'>
            <SymbolReasons title='Blocked Today' rows={blocked} />
            <SymbolReasons title='Watch Only' rows={watchOnly} />
            {!isLoading && Object.keys(blocked).length === 0 && Object.keys(watchOnly).length === 0 && (
              <div className='flex items-center gap-2 rounded-md border border-[var(--to-border)] bg-[var(--to-surface-raised)] p-3 text-xs text-[var(--to-text-dim)]'>
                <CheckCircle2 className='h-4 w-4 text-[var(--to-text-secondary)]' />
                No active block reasons reported.
              </div>
            )}
          </div>
        </div>
      </div>
    </section>
  );
}
