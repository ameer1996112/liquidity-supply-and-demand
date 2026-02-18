'use client';

import { useState } from 'react';
import { useRiskStatus, useKillSwitchMutation } from '@/hooks/useRiskStatus';
import { Shield, AlertTriangle, Power } from 'lucide-react';
import { cn } from '@/lib/utils';

/* ── Mini progress bar for risk gauges ───────────────────── */

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
    <div className='flex min-w-[122px] flex-col gap-1'>
      <div className='flex items-center justify-between'>
        <span className='font-mono text-[9px] uppercase tracking-[0.14em] text-[#8e9dbf]'>
          {label}
        </span>
        <span
          className={cn(
            'text-[10px] font-mono font-semibold tabular-nums',
            danger ? 'text-[#ff7e92]' : 'text-[#dbe5f8]'
          )}
        >
          {value}
          {unit}
        </span>
      </div>
      <div className='h-1.5 overflow-hidden rounded-full bg-[rgba(36,50,78,0.72)]'>
        <div
          className={cn(
            'h-full rounded-full transition-all duration-500',
            danger ? 'bg-[#ff7e92]' : 'bg-[#3fc7ad]'
          )}
          style={{ width: `${pct}%` }}
        />
      </div>
    </div>
  );
}

/* ── Main risk bar ───────────────────────────────────────── */

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
  const dailyDrawdownPct = dailyPnlPctForDanger;
  const dailyDrawdownDanger = dailyDrawdownPct > risk.max_daily_loss_pct * 0.7;
  const positionsDanger = risk.active_positions >= risk.max_positions;

  return (
    <div className='relative flex items-center gap-3 rounded-xl border border-[rgba(110,131,170,0.34)] bg-[rgba(14,22,38,0.9)] px-3 py-2'>
      {/* Gauges - Daily P&L removed (TopBar already shows Daily PnL) */}
      <RiskGauge
        label='Drawdown'
        value={risk.drawdown_pct.toFixed(1)}
        max={risk.max_drawdown_pct}
        unit='%'
        danger={drawdownDanger}
      />
      <RiskGauge
        label='Daily DD'
        value={dailyDrawdownPct.toFixed(1)}
        max={risk.max_daily_loss_pct}
        unit='%'
        danger={dailyDrawdownDanger}
      />

      {/* Positions counter */}
      <div className='flex items-center gap-1.5'>
        <span className='font-mono text-[9px] uppercase tracking-[0.14em] text-[#8e9dbf]'>
          Pos
        </span>
        <span
          className={cn(
            'font-mono text-xs font-semibold tabular-nums',
            positionsDanger ? 'text-[#ff7e92]' : 'text-[#dbe5f8]'
          )}
        >
          {risk.active_positions}/{risk.max_positions}
        </span>
      </div>

      {/* Risk mode badge */}
      <div className='flex items-center gap-1 rounded-lg border border-[rgba(110,131,170,0.34)] bg-[rgba(26,39,62,0.8)] px-2 py-1'>
        <Shield className='h-3 w-3 text-[#9aadd3]' />
        <span className='font-mono text-[9px] uppercase text-[#bed0f2]'>
          {risk.risk_label}
        </span>
      </div>

      {/* Kill switch toggle */}
      <button
        onClick={handleToggle}
        disabled={killMutation.isPending}
        className={cn(
          'flex items-center gap-1.5 rounded-lg border px-2.5 py-1',
          'font-mono text-[10px] font-semibold uppercase tracking-wider transition-all',
          risk.kill_switch_active
            ? 'animate-pulse border-[#ff7e92] bg-[#ff7e92] text-white'
            : 'border-[rgba(110,131,170,0.34)] bg-[rgba(26,39,62,0.8)] text-[#c7d4ed] hover:border-[rgba(138,160,202,0.62)] hover:text-[#eef3fb]'
        )}
      >
        <Power className='h-3.5 w-3.5' />
        {risk.kill_switch_active ? 'KILL ACTIVE' : 'KILL SWITCH'}
      </button>

      {/* Confirm dialog */}
      {showConfirm && (
        <div className='absolute right-0 top-10 z-50 min-w-[230px] rounded-xl border border-[rgba(110,131,170,0.46)] bg-[rgba(14,22,38,0.98)] p-4 shadow-[0_18px_36px_rgba(3,8,16,0.6)]'>
          <div className='mb-2 flex items-center gap-2'>
            <AlertTriangle className='h-4 w-4 text-[#ffb14f]' />
            <span className='text-xs font-semibold text-[#dce7ff]'>
              Reset Kill Switch?
            </span>
          </div>
          <p className='mb-3 text-[11px] text-[#93a5c8]'>
            This will allow trading to resume.
          </p>
          <div className='flex gap-2'>
            <button
              onClick={confirmDisengage}
              className='rounded-md border border-[rgba(46,201,170,0.45)] bg-[rgba(46,201,170,0.2)] px-3 py-1 font-mono text-[10px] font-semibold text-[#dff9f3]'
            >
              Confirm
            </button>
            <button
              onClick={() => setShowConfirm(false)}
              className='rounded-md border border-[rgba(95,119,163,0.32)] bg-[rgba(24,37,59,0.78)] px-3 py-1 font-mono text-[10px] text-[#b8c7e4]'
            >
              Cancel
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
