'use client';

import { useState, type ComponentType } from 'react';
import { cn } from '@/lib/utils';
import type { GuardConfig, GuardsConfigResponse } from '@/hooks/useGuards';
import {
  Shield,
  ShieldAlert,
  ShieldCheck,
  ShieldOff,
  TrendingDown,
  Zap,
  Brain,
  Timer,
  CalendarOff,
  Clock,
  Activity,
  Lock,
  BarChart3,
  AlertTriangle,
  ChevronDown,
  ChevronRight,
  Info,
  Loader2,
} from 'lucide-react';

const TIER_TOKENS = {
  critical: {
    border: 'border-[#f6465d]/25',
    borderHover: 'hover:border-[#f6465d]/45',
    bg: 'bg-gradient-to-br from-[#f6465d]/[0.04] to-[var(--to-surface)]',
    bgDisabled: 'bg-[var(--to-surface)]',
    iconBg: 'bg-[#f6465d]/10',
    iconColor: 'text-[#f6465d]',
    glow: 'shadow-[0_0_12px_rgba(246,70,93,0.08)]',
    badge: 'bg-[#f6465d]/15 text-[#f6465d] border border-[#f6465d]/20',
    accent: '#f6465d',
    label: 'Critical',
  },
  important: {
    border: 'border-[#f0b90b]/20',
    borderHover: 'hover:border-[#f0b90b]/40',
    bg: 'bg-gradient-to-br from-[#f0b90b]/[0.03] to-[var(--to-surface)]',
    bgDisabled: 'bg-[var(--to-surface)]',
    iconBg: 'bg-[#f0b90b]/10',
    iconColor: 'text-[#f0b90b]',
    glow: 'shadow-[0_0_12px_rgba(240,185,11,0.06)]',
    badge: 'bg-[#f0b90b]/15 text-[#f0b90b] border border-[#f0b90b]/20',
    accent: '#f0b90b',
    label: 'Important',
  },
  convenience: {
    border: 'border-[#0ecb81]/20',
    borderHover: 'hover:border-[#0ecb81]/40',
    bg: 'bg-gradient-to-br from-[#0ecb81]/[0.03] to-[var(--to-surface)]',
    bgDisabled: 'bg-[var(--to-surface)]',
    iconBg: 'bg-[#0ecb81]/10',
    iconColor: 'text-[#0ecb81]',
    glow: '',
    badge: 'bg-[#0ecb81]/15 text-[#0ecb81] border border-[#0ecb81]/20',
    accent: '#0ecb81',
    label: 'Optional',
  },
} as const;

const GUARD_ICONS: Record<string, ComponentType<{ className?: string }>> = {
  kill_switch: ShieldAlert,
  daily_loss_limit: TrendingDown,
  max_drawdown: TrendingDown,
  max_lot_size: BarChart3,
  weekly_loss_limit: TrendingDown,
  monthly_loss_limit: TrendingDown,
  prop_guard: Shield,
  staleness_guard: Timer,
  correlation_guard: Activity,
  ai_debate: Brain,
  daily_trade_limit: BarChart3,
  spread_gate: Zap,
  circuit_breaker: AlertTriangle,
  htf_candle_filter: Clock,
  one_candle_liq_filter: Activity,
  holiday_guard: CalendarOff,
  mtm_guardian: ShieldCheck,
  swap_guard: CalendarOff,
};

const GROUP_ORDER = ['capital_protection', 'trade_quality', 'scheduling'];

const GROUP_ICONS: Record<string, ComponentType<{ className?: string }>> = {
  capital_protection: ShieldAlert,
  trade_quality: Brain,
  scheduling: CalendarOff,
};

function Toggle({
  checked,
  onChange,
  disabled,
}: {
  checked: boolean;
  onChange: (v: boolean) => void;
  disabled?: boolean;
}) {
  return (
    <button
      type="button"
      role="switch"
      aria-checked={checked}
      onClick={() => onChange(!checked)}
      disabled={disabled}
      className={cn(
        'relative inline-flex h-5 w-9 items-center rounded-full transition-colors',
        checked ? 'bg-[#0ecb81]' : 'bg-[var(--to-border)]',
        disabled && 'opacity-40 cursor-not-allowed',
      )}
    >
      <span
        className={cn(
          'inline-block h-3.5 w-3.5 transform rounded-full bg-white shadow-sm transition-transform',
          checked ? 'translate-x-[18px]' : 'translate-x-[3px]',
        )}
      />
    </button>
  );
}

function ThresholdEditor({
  threshold,
  onUpdate,
  disabled,
}: {
  threshold: GuardConfig['thresholds'][number];
  onUpdate: (key: string, value: number | boolean) => void;
  disabled?: boolean;
}) {
  if (threshold.value_type === 'bool') {
    return (
      <div className="flex items-center justify-between py-2">
        <span className="text-[11px] text-[var(--to-text-secondary)]">{threshold.name}</span>
        <Toggle
          checked={Boolean(threshold.current_value)}
          onChange={(v) => onUpdate(threshold.setting_key, v)}
          disabled={disabled}
        />
      </div>
    );
  }

  return (
    <div className="flex items-center justify-between gap-3 py-2">
      <span className="text-[11px] text-[var(--to-text-secondary)] shrink-0">{threshold.name}</span>
      <div className="flex items-center gap-1.5">
        <input
          type="number"
          value={threshold.current_value as number}
          onChange={(e) => {
            const val = threshold.value_type === 'int' ? parseInt(e.target.value, 10) : parseFloat(e.target.value);
            if (!isNaN(val)) onUpdate(threshold.setting_key, val);
          }}
          min={threshold.min_value ?? undefined}
          max={threshold.max_value ?? undefined}
          step={threshold.value_type === 'int' ? 1 : 0.1}
          disabled={disabled}
          className="w-20 rounded-md border border-[var(--to-border)] bg-[var(--to-bg)] px-2 py-1 text-right text-xs text-white font-mono focus:outline-none focus:ring-1 focus:ring-indigo-500/50 disabled:opacity-40"
        />
        {threshold.unit && <span className="text-[10px] text-[var(--to-text-dim)] w-8 font-mono">{threshold.unit}</span>}
      </div>
    </div>
  );
}

function GuardCard({
  guard,
  scopeLabel,
  onToggle,
  onThresholdUpdate,
  isUpdating,
}: {
  guard: GuardConfig;
  scopeLabel: string;
  onToggle: (guard: GuardConfig) => void;
  onThresholdUpdate: (guardId: string, key: string, value: number | boolean) => void;
  isUpdating: boolean;
}) {
  const [expanded, setExpanded] = useState(false);
  const t = TIER_TOKENS[guard.tier as keyof typeof TIER_TOKENS] ?? TIER_TOKENS.convenience;
  const Icon = GUARD_ICONS[guard.guard_id] ?? Shield;
  const isEnabled = guard.value_type === 'bool' ? Boolean(guard.enabled) : true;
  const isExpandable = guard.thresholds.length > 0 || guard.value_type !== 'bool';

  return (
    <div
      className={cn(
        'group rounded-xl border transition-all duration-200',
        isEnabled ? [t.border, t.bg, t.glow, t.borderHover] : [t.border, t.bgDisabled, 'opacity-60'],
      )}
    >
      <div className="flex items-center gap-3 px-4 py-3">
        <div className={cn('flex h-8 w-8 shrink-0 items-center justify-center rounded-lg transition-colors', isEnabled ? t.iconBg : 'bg-[var(--to-surface-raised)]')}>
          <Icon className={cn('h-3.5 w-3.5', isEnabled ? t.iconColor : 'text-[var(--to-text-dim)]')} />
        </div>
        <div className="min-w-0 flex-1">
          <div className="flex items-center gap-2 flex-wrap">
            <span className="text-[13px] font-medium text-[var(--to-text-primary)] truncate">{guard.name}</span>
            {guard.tier === 'critical' && <Lock className="h-3 w-3 shrink-0 text-[#f6465d]/60" />}
            <span className="text-[9px] font-mono text-[var(--to-text-dim)] bg-[var(--to-surface-raised)] px-1.5 py-0.5 rounded">
              {scopeLabel}
            </span>
            {guard.rejection_count_7d > 0 && (
              <span className={cn('shrink-0 inline-flex items-center rounded-md px-1.5 py-0.5 text-[9px] font-mono font-medium', t.badge)}>
                {guard.rejection_count_7d} blocked
              </span>
            )}
          </div>
          <div className="flex items-center gap-1.5 mt-0.5 flex-wrap">
            {guard.thresholds.length > 0 ? (
              guard.thresholds.filter((th) => th.value_type !== 'bool').map((th) => (
                <span
                  key={th.setting_key}
                  className="inline-flex items-center gap-0.5 rounded bg-[var(--to-surface-raised)] border border-[var(--to-border-subtle)] px-1.5 py-0.5 text-[9px] font-mono text-[var(--to-text-secondary)]"
                >
                  <span className="text-[var(--to-text-dim)]">{th.name}:</span>
                  <span className="text-[var(--to-text-primary)]">{th.current_value}</span>
                  {th.unit && <span className="text-[var(--to-text-dim)]">{th.unit}</span>}
                </span>
              ))
            ) : (
              <p className="text-[10px] text-[var(--to-text-dim)] truncate">{guard.user_description}</p>
            )}
          </div>
        </div>
        <div className="flex items-center gap-2 shrink-0">
          {guard.value_type !== 'bool' && (
            <span className="text-xs font-mono text-[var(--to-text-primary)] bg-[var(--to-surface-raised)] border border-[var(--to-border)] px-2 py-0.5 rounded-md">
              {guard.enabled}
              {guard.unit && <span className="text-[var(--to-text-dim)] ml-0.5">{guard.unit}</span>}
            </span>
          )}
          {isUpdating && <Loader2 className="h-3.5 w-3.5 animate-spin text-[#f0b90b]" />}
          {guard.value_type === 'bool' && <Toggle checked={isEnabled} onChange={() => onToggle(guard)} disabled={isUpdating} />}
          {isExpandable && (
            <button
              onClick={() => setExpanded(!expanded)}
              className="flex h-6 w-6 items-center justify-center rounded-md text-[var(--to-text-dim)] hover:text-[var(--to-text-secondary)] hover:bg-[var(--to-surface-raised)] transition-colors"
            >
              {expanded ? <ChevronDown className="h-3.5 w-3.5" /> : <ChevronRight className="h-3.5 w-3.5" />}
            </button>
          )}
        </div>
      </div>

      {expanded && (
        <div className="border-t border-[var(--to-border-subtle)] mx-4 py-3 space-y-0.5">
          {guard.value_type !== 'bool' && (
            <div className="flex items-center justify-between gap-3 py-2 mb-1 border-b border-[var(--to-border-subtle)] pb-3">
              <span className="text-[11px] text-[var(--to-text-primary)] font-medium">{guard.name}</span>
              <div className="flex items-center gap-1.5">
                <input
                  type="number"
                  value={guard.enabled as number}
                  onChange={(e) => {
                    const val = guard.value_type === 'int' ? parseInt(e.target.value, 10) : parseFloat(e.target.value);
                    if (!isNaN(val)) onThresholdUpdate(guard.guard_id, '__primary__', val);
                  }}
                  min={guard.min_value ?? undefined}
                  max={guard.max_value ?? undefined}
                  step={guard.value_type === 'int' ? 1 : 0.1}
                  disabled={isUpdating}
                  className="w-20 rounded-md border border-[var(--to-border)] bg-[var(--to-bg)] px-2 py-1 text-right text-xs text-white font-mono focus:outline-none focus:ring-1 focus:ring-indigo-500/50 disabled:opacity-40"
                />
                {guard.unit && <span className="text-[10px] text-[var(--to-text-dim)] w-8 font-mono">{guard.unit}</span>}
              </div>
            </div>
          )}
          {guard.thresholds.map((th) => (
            <ThresholdEditor key={th.setting_key} threshold={th} onUpdate={(key, val) => onThresholdUpdate(guard.guard_id, key, val)} disabled={isUpdating} />
          ))}
          <div className="flex items-start gap-2 mt-2 pt-2.5 border-t border-[var(--to-border-subtle)]">
            <Info className="h-3 w-3 text-[var(--to-text-dim)] shrink-0 mt-0.5" />
            <p className="text-[10px] text-[var(--to-text-dim)] leading-relaxed">{guard.user_description}</p>
          </div>
        </div>
      )}
    </div>
  );
}

function KpiCard({
  label,
  value,
  sub,
  accent,
}: {
  label: string;
  value: string | number;
  sub?: string;
  accent: string;
}) {
  return (
    <div className="to-panel flex-1 min-w-[140px] px-4 py-3">
      <p className="text-[10px] uppercase tracking-wider text-[var(--to-text-dim)] mb-1">{label}</p>
      <p className="text-xl font-semibold font-mono" style={{ color: accent }}>{value}</p>
      {sub && <p className="text-[10px] text-[var(--to-text-dim)] mt-0.5 font-mono">{sub}</p>}
    </div>
  );
}

export function GuardGroupList({
  data,
  scopeLabel,
  savingGuards,
  onToggle,
  onThresholdUpdate,
}: {
  data: GuardsConfigResponse;
  scopeLabel: string;
  savingGuards: Set<string>;
  onToggle: (guard: GuardConfig) => void;
  onThresholdUpdate: (guardId: string, key: string, value: number | boolean) => void;
}) {
  const { groups, group_labels, total_rejections_7d, total_signals_7d } = data;
  const allGuards = Object.values(groups).flat();
  const enabledCount = allGuards.filter((g) => g.value_type !== 'bool' || g.enabled).length;
  const criticalCount = allGuards.filter((g) => g.tier === 'critical').length;
  const rejectionPct = total_signals_7d > 0 ? ((total_rejections_7d / total_signals_7d) * 100).toFixed(1) : '0';

  return (
    <div className="space-y-6">
      <div className="flex gap-3 flex-wrap">
        <KpiCard label="Active Guards" value={enabledCount} sub={`of ${allGuards.length} total`} accent="#0ecb81" />
        <KpiCard label="Critical Guards" value={criticalCount} sub="always recommended" accent="#f6465d" />
        <KpiCard
          label="Signals Blocked (7d)"
          value={total_rejections_7d}
          sub={total_signals_7d > 0 ? `${rejectionPct}% of ${total_signals_7d} signals` : 'no signals yet'}
          accent="#f0b90b"
        />
      </div>

      {GROUP_ORDER.map((groupKey) => {
        const guards = groups[groupKey];
        if (!guards || guards.length === 0) return null;
        const label = group_labels[groupKey] || groupKey;
        const GroupIcon = GROUP_ICONS[groupKey] ?? Shield;

        return (
          <div key={groupKey} className="to-panel overflow-hidden">
            <div className="to-panel-header">
              <div className="flex items-center gap-2">
                <GroupIcon className="h-3.5 w-3.5 text-[var(--to-text-dim)]" />
                <span className="to-panel-title">{label}</span>
                <span className="text-[10px] font-mono text-[var(--to-text-dim)] bg-[var(--to-surface-raised)] px-1.5 py-0.5 rounded">
                  {guards.length}
                </span>
              </div>
            </div>
            <div className="p-3 space-y-2">
              {guards.map((guard) => (
                <GuardCard
                  key={guard.guard_id}
                  guard={guard}
                  scopeLabel={scopeLabel}
                  onToggle={onToggle}
                  onThresholdUpdate={onThresholdUpdate}
                  isUpdating={savingGuards.has(guard.guard_id)}
                />
              ))}
            </div>
          </div>
        );
      })}
    </div>
  );
}
