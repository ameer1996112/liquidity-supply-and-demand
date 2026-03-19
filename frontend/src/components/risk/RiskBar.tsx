'use client';

import { useState } from 'react';
import { useRiskStatus, useKillSwitchMutation } from '@/hooks/useRiskStatus';
import { Shield, Power } from 'lucide-react';
import { cn } from '@/lib/utils';
import {
  KillSwitchConfirmDialog,
  type KillSwitchMode,
} from '@/components/risk/KillSwitchConfirmDialog';

function RiskGauge({
  label,
  value,
  max,
  unit,
  danger,
}: {
  label: string;
  value: string;
  max: number;
  unit: string;
  danger: boolean;
}) {
  const numericValue = parseFloat(value) || 0;
  const pct = max > 0 ? Math.min((Math.abs(numericValue) / max) * 100, 100) : 0;

  return (
    <div className='flex min-w-[110px] flex-1 flex-col gap-1'>
      <div className='flex items-center justify-between'>
        <span
          className='text-[9px] uppercase tracking-[0.12em] text-[var(--to-text-dim)]'
          style={{ fontFamily: 'var(--font-sans)' }}
        >
          {label}
        </span>
        <span
          className={cn(
            'text-[11px] font-semibold tabular-nums',
            danger ? 'text-[var(--to-short)]' : 'text-slate-300'
          )}
          style={{ fontFamily: 'var(--font-mono)' }}
        >
          {value}
          {unit}
        </span>
      </div>
      <div className='h-1 overflow-hidden rounded-full bg-slate-800'>
        <div
          className={cn(
            'h-full rounded-full transition-all duration-500',
            danger ? 'bg-red-400' : 'bg-emerald-500'
          )}
          style={{ width: `${pct}%` }}
        />
      </div>
    </div>
  );
}

export function RiskBar() {
  const { data: risk, isLoading } = useRiskStatus();
  const killMutation = useKillSwitchMutation();
  const [killDialogOpen, setKillDialogOpen] = useState(false);
  const [killDialogMode, setKillDialogMode] = useState<KillSwitchMode>('engage');

  if (isLoading || !risk) return null;

  const dailyPnlPctForDanger =
    risk.starting_equity > 0 && (risk.live_daily_pnl ?? risk.daily_pnl) < 0
      ? (Math.abs(risk.live_daily_pnl ?? risk.daily_pnl) /
          risk.starting_equity) *
        100
      : 0;

  const drawdownDanger = risk.drawdown_pct > risk.max_drawdown_pct * 0.7;
  const dailyDrawdownDanger =
    dailyPnlPctForDanger > risk.max_daily_loss_pct * 0.7;
  const positionsDanger = risk.active_positions >= risk.max_positions;

  const handleKillClick = () => {
    const mode: KillSwitchMode = risk.kill_switch_active ? 'reset' : 'engage';
    setKillDialogMode(mode);
    setKillDialogOpen(true);
  };

  return (
    <div className='relative flex flex-wrap items-center gap-3 rounded-lg border border-slate-800 bg-slate-900/80 px-3 py-2'>
      {/* Gauges */}
      <RiskGauge
        label='Drawdown'
        value={risk.drawdown_pct.toFixed(1)}
        max={risk.max_drawdown_pct}
        unit='%'
        danger={drawdownDanger}
      />
      <RiskGauge
        label='Daily DD'
        value={dailyPnlPctForDanger.toFixed(1)}
        max={risk.max_daily_loss_pct}
        unit='%'
        danger={dailyDrawdownDanger}
      />

      {/* Positions counter */}
      <div className='flex items-center gap-1.5'>
        <span
          className='text-[9px] uppercase tracking-[0.12em] text-[var(--to-text-dim)]'
          style={{ fontFamily: 'var(--font-sans)' }}
        >
          Pos
        </span>
        <span
          className={cn(
            'text-[11px] font-semibold tabular-nums',
            positionsDanger ? 'text-[var(--to-short)]' : 'text-slate-300'
          )}
          style={{ fontFamily: 'var(--font-mono)' }}
        >
          {risk.active_positions}/{risk.max_positions}
        </span>
      </div>

      {/* Risk mode badge */}
      <div className='flex items-center gap-1 rounded-md border border-slate-800 bg-slate-800/60 px-2 py-1'>
        <Shield className='h-3 w-3 text-[var(--to-text-dim)]' />
        <span
          className='text-[9px] uppercase text-[var(--to-text-dim)]'
          style={{ fontFamily: 'var(--font-mono)' }}
        >
          {risk.risk_label}
        </span>
      </div>

      {/* Kill switch */}
      <button
        onClick={handleKillClick}
        disabled={killMutation.isPending}
        className={cn(
          'flex items-center gap-1.5 rounded-md border px-2.5 py-1',
          'text-[10px] font-semibold uppercase tracking-wider transition-all',
          risk.kill_switch_active
            ? 'animate-pulse border-red-500 bg-[var(--to-short)]/20 text-red-300'
            : 'border-slate-700 bg-slate-800/60 text-[var(--to-text-dim)] hover:border-slate-600 hover:text-slate-200'
        )}
        style={{ fontFamily: 'var(--font-mono)' }}
      >
        <Power className='h-3 w-3' />
        {risk.kill_switch_active ? 'KILL ACTIVE' : 'KILL SWITCH'}
      </button>
      <KillSwitchConfirmDialog
        open={killDialogOpen}
        mode={killDialogMode}
        onOpenChange={setKillDialogOpen}
        isPending={killMutation.isPending}
        onConfirm={(reason) => {
          const enabled = killDialogMode === 'engage';
          killMutation.mutate({ enabled, reason });
          setKillDialogOpen(false);
        }}
      />
    </div>
  );
}
