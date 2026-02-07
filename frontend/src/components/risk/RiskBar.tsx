'use client';

import { useState } from 'react';
import {
  useRiskStatus,
  useKillSwitchMutation,
} from '@/hooks/useRiskStatus';
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
    <div className="flex flex-col gap-0.5 min-w-[110px]">
      <div className="flex items-center justify-between">
        <span className="text-[9px] uppercase tracking-wider text-zinc-500 font-mono">
          {label}
        </span>
        <span
          className={cn(
            'text-[10px] font-mono font-semibold tabular-nums',
            danger ? 'text-[#ef5350]' : 'text-zinc-300',
          )}
        >
          {value}
          {unit}
        </span>
      </div>
      <div className="h-1 bg-[#2a2e39] rounded-full overflow-hidden">
        <div
          className={cn(
            'h-full rounded-full transition-all duration-500',
            danger ? 'bg-[#ef5350]' : 'bg-[#26a69a]',
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
      ? (Math.abs(risk.live_daily_pnl ?? risk.daily_pnl) / risk.starting_equity) * 100
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
    <div className="flex items-center gap-4 relative">
      {/* Gauges - Daily P&L removed (TopBar already shows Daily PnL) */}
      <RiskGauge
        label="Drawdown"
        value={risk.drawdown_pct.toFixed(1)}
        max={risk.max_drawdown_pct}
        unit="%"
        danger={drawdownDanger}
      />
      <RiskGauge
        label="Daily DD"
        value={dailyDrawdownPct.toFixed(1)}
        max={risk.max_daily_loss_pct}
        unit="%"
        danger={dailyDrawdownDanger}
      />

      {/* Positions counter */}
      <div className="flex items-center gap-1.5">
        <span className="text-[9px] uppercase tracking-wider text-zinc-500 font-mono">
          Pos
        </span>
        <span
          className={cn(
            'font-mono text-xs font-semibold tabular-nums',
            positionsDanger ? 'text-[#ef5350]' : 'text-zinc-300',
          )}
        >
          {risk.active_positions}/{risk.max_positions}
        </span>
      </div>

      {/* Risk mode badge */}
      <div className="flex items-center gap-1 px-1.5 py-0.5 rounded bg-[#1e222d]">
        <Shield className="w-3 h-3 text-zinc-500" />
        <span className="text-[9px] font-mono text-zinc-400 uppercase">
          {risk.risk_label}
        </span>
      </div>

      {/* Kill switch toggle */}
      <button
        onClick={handleToggle}
        disabled={killMutation.isPending}
        className={cn(
          'flex items-center gap-1.5 px-2.5 py-1 rounded-md',
          'font-mono text-[10px] font-semibold uppercase tracking-wider transition-all',
          risk.kill_switch_active
            ? 'bg-[#ef5350] text-white animate-pulse'
            : 'bg-[#1e222d] text-zinc-400 hover:text-zinc-200 hover:bg-[#2a2e39]',
        )}
      >
        <Power className="w-3.5 h-3.5" />
        {risk.kill_switch_active ? 'KILL ACTIVE' : 'KILL SWITCH'}
      </button>

      {/* Confirm dialog */}
      {showConfirm && (
        <div className="absolute top-10 right-0 z-50 bg-[#1e222d] border border-[#2a2e39] rounded-lg p-4 shadow-xl min-w-[220px]">
          <div className="flex items-center gap-2 mb-2">
            <AlertTriangle className="w-4 h-4 text-amber-500" />
            <span className="text-xs text-zinc-300 font-semibold">
              Reset Kill Switch?
            </span>
          </div>
          <p className="text-[11px] text-zinc-500 mb-3">
            This will allow trading to resume.
          </p>
          <div className="flex gap-2">
            <button
              onClick={confirmDisengage}
              className="px-3 py-1 bg-[#26a69a] text-white rounded text-[10px] font-mono font-semibold"
            >
              Confirm
            </button>
            <button
              onClick={() => setShowConfirm(false)}
              className="px-3 py-1 bg-[#2a2e39] text-zinc-400 rounded text-[10px] font-mono"
            >
              Cancel
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
