'use client';

import { useState } from 'react';
import { useRiskStatus, useKillSwitchMutation } from '@/hooks/useRiskStatus';
import { Shield, AlertTriangle, Power } from 'lucide-react';
import { cn } from '@/lib/utils';

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
    <div className='flex min-w-[110px] flex-col gap-1'>
      <div className='flex items-center justify-between'>
        <span
          className='text-[9px] uppercase tracking-[0.12em] text-slate-500'
          style={{ fontFamily: 'var(--font-sans)' }}
        >
          {label}
        </span>
        <span
          className={cn(
            'text-[11px] font-semibold tabular-nums',
            danger ? 'text-red-400' : 'text-slate-300'
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
  const [showConfirm, setShowConfirm] = useState(false);

  if (isLoading || !risk) return null;

  const dailyPnlPctForDanger =
    risk.starting_equity > 0 && (risk.live_daily_pnl ?? risk.daily_pnl) < 0
      ? (Math.abs(risk.live_daily_pnl ?? risk.daily_pnl) /
          risk.starting_equity) *
        100
      : 0;

  const handleToggle = () => {
    if (risk.kill_switch_active) {
      setShowConfirm(true);
    } else {
      killMutation.mutate({ enabled: true, reason: 'Manual UI toggle' });
    }
  };

  const confirmDisengage = () => {
    killMutation.mutate({ enabled: false, reason: 'Manual UI reset' });
    setShowConfirm(false);
  };

  const drawdownDanger = risk.drawdown_pct > risk.max_drawdown_pct * 0.7;
  const dailyDrawdownDanger =
    dailyPnlPctForDanger > risk.max_daily_loss_pct * 0.7;
  const positionsDanger = risk.active_positions >= risk.max_positions;

  return (
    <div className='relative flex items-center gap-3 rounded-lg border border-slate-800 bg-slate-900/80 px-3 py-2'>
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
          className='text-[9px] uppercase tracking-[0.12em] text-slate-500'
          style={{ fontFamily: 'var(--font-sans)' }}
        >
          Pos
        </span>
        <span
          className={cn(
            'text-[11px] font-semibold tabular-nums',
            positionsDanger ? 'text-red-400' : 'text-slate-300'
          )}
          style={{ fontFamily: 'var(--font-mono)' }}
        >
          {risk.active_positions}/{risk.max_positions}
        </span>
      </div>

      {/* Risk mode badge */}
      <div className='flex items-center gap-1 rounded-md border border-slate-800 bg-slate-800/60 px-2 py-1'>
        <Shield className='h-3 w-3 text-slate-500' />
        <span
          className='text-[9px] uppercase text-slate-400'
          style={{ fontFamily: 'var(--font-mono)' }}
        >
          {risk.risk_label}
        </span>
      </div>

      {/* Kill switch */}
      <button
        onClick={handleToggle}
        disabled={killMutation.isPending}
        className={cn(
          'flex items-center gap-1.5 rounded-md border px-2.5 py-1',
          'text-[10px] font-semibold uppercase tracking-wider transition-all',
          risk.kill_switch_active
            ? 'animate-pulse border-red-500 bg-red-500/20 text-red-300'
            : 'border-slate-700 bg-slate-800/60 text-slate-400 hover:border-slate-600 hover:text-slate-200'
        )}
        style={{ fontFamily: 'var(--font-mono)' }}
      >
        <Power className='h-3 w-3' />
        {risk.kill_switch_active ? 'KILL ACTIVE' : 'KILL SWITCH'}
      </button>

      {/* Confirm dialog */}
      {showConfirm && (
        <div className='absolute right-0 top-10 z-50 min-w-[220px] rounded-lg border border-slate-700 bg-slate-900 p-4 shadow-xl'>
          <div className='mb-2 flex items-center gap-2'>
            <AlertTriangle className='h-3.5 w-3.5 text-amber-400' />
            <span
              className='text-xs font-semibold text-slate-200'
              style={{ fontFamily: 'var(--font-sans)' }}
            >
              Reset Kill Switch?
            </span>
          </div>
          <p
            className='mb-3 text-[11px] text-slate-500'
            style={{ fontFamily: 'var(--font-sans)' }}
          >
            This will allow trading to resume.
          </p>
          <div className='flex gap-2'>
            <button
              onClick={confirmDisengage}
              className='rounded-md border border-emerald-500/30 bg-emerald-500/15 px-3 py-1 text-[10px] font-semibold text-emerald-400'
              style={{ fontFamily: 'var(--font-mono)' }}
            >
              Confirm
            </button>
            <button
              onClick={() => setShowConfirm(false)}
              className='rounded-md border border-slate-700 bg-slate-800 px-3 py-1 text-[10px] text-slate-400'
              style={{ fontFamily: 'var(--font-mono)' }}
            >
              Cancel
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
