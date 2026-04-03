'use client';

import { useState, useCallback } from 'react';
import { cn } from '@/lib/utils';
import {
  useGuardsConfig,
  useUpdateGuard,
  type GuardConfig,
  type ThresholdConfig,
  type DynamicThresholdInfo,
} from '@/hooks/useGuards';
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
  ShieldX,
} from 'lucide-react';

/* ═══════════════════════════════════════════════════════════
   TIER DESIGN TOKENS — Maps to TradeOps glow system
   ═══════════════════════════════════════════════════════════ */

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

const GUARD_ICONS: Record<string, React.ComponentType<{ className?: string }>> = {
  kill_switch: ShieldAlert,
  daily_loss_limit: TrendingDown,
  max_drawdown: TrendingDown,
  max_lot_size: BarChart3,
  weekly_loss_limit: TrendingDown,
  monthly_loss_limit: TrendingDown,
  prop_guard: Shield,
  staleness_guard: Timer,
  correlation_guard: Activity,
  ai_filter: Brain,
  daily_trade_limit: BarChart3,
  spread_gate: Zap,
  circuit_breaker: AlertTriangle,
  htf_candle_filter: Clock,
  one_candle_liq_filter: Activity,
  holiday_guard: CalendarOff,
  dead_zone: Clock,
  mtm_guardian: ShieldCheck,
};

const GROUP_ORDER = ['capital_protection', 'trade_quality', 'scheduling'];

const GROUP_ICONS: Record<string, React.ComponentType<{ className?: string }>> = {
  capital_protection: ShieldAlert,
  trade_quality: Brain,
  scheduling: CalendarOff,
};

/* ═══════════════════════════════════════════════════════════
   TOGGLE SWITCH — Matches TradeOps green/neutral scheme
   ═══════════════════════════════════════════════════════════ */

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

/* ═══════════════════════════════════════════════════════════
   CONFIRMATION DIALOG — Glass panel overlay
   ═══════════════════════════════════════════════════════════ */

function ConfirmDialog({
  guard,
  action,
  onConfirm,
  onCancel,
}: {
  guard: GuardConfig;
  action: 'disable' | 'enable';
  onConfirm: (reason: string) => void;
  onCancel: () => void;
}) {
  const [reason, setReason] = useState('');
  const [confirmText, setConfirmText] = useState('');
  const isCritical = guard.tier === 'critical';
  const requiresType = isCritical && action === 'disable';
  const canConfirm = requiresType
    ? confirmText === 'DISABLE' && reason.trim().length > 0
    : true;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 backdrop-blur-sm">
      <div
        className={cn(
          'glass-panel-strong w-full max-w-md p-6',
          'border border-[var(--to-border)] rounded-xl',
          'bg-gradient-to-br from-[var(--to-surface)] to-[var(--to-surface-raised)]',
          'shadow-[0_25px_50px_-12px_rgba(0,0,0,0.5)]',
        )}
      >
        {/* Header */}
        <div className="flex items-center gap-3 mb-5">
          <div
            className={cn(
              'flex h-10 w-10 items-center justify-center rounded-xl',
              action === 'disable' ? 'bg-[#f6465d]/15' : 'bg-[#0ecb81]/15',
            )}
          >
            {action === 'disable' ? (
              <ShieldOff className="h-5 w-5 text-[#f6465d]" />
            ) : (
              <ShieldCheck className="h-5 w-5 text-[#0ecb81]" />
            )}
          </div>
          <div>
            <h3 className="text-sm font-semibold text-[var(--to-text-primary)]">
              {action === 'disable' ? 'Disable' : 'Enable'} {guard.name}
            </h3>
            <p className="text-[10px] uppercase tracking-wider text-[var(--to-text-dim)]">
              {TIER_TOKENS[guard.tier as keyof typeof TIER_TOKENS]?.label ?? guard.tier} guard
            </p>
          </div>
        </div>

        <p className="mb-4 text-xs text-[var(--to-text-secondary)] leading-relaxed">
          {action === 'disable'
            ? guard.user_description
            : `Re-enabling "${guard.name}" will restore this protection.`}
        </p>

        {/* Critical type-to-confirm */}
        {isCritical && action === 'disable' && (
          <div className="mb-4 rounded-lg border border-[#f6465d]/30 bg-[#f6465d]/[0.06] p-3.5">
            <p className="text-[11px] text-[#f6465d]/90 mb-2.5 leading-relaxed">
              This is a capital protection guard. Disabling it may expose your account to significant risk.
            </p>
            <p className="text-[11px] text-[#f6465d] font-medium">
              Type{' '}
              <code className="font-mono bg-[#f6465d]/15 px-1.5 py-0.5 rounded text-[10px]">
                DISABLE
              </code>{' '}
              to confirm:
            </p>
            <input
              type="text"
              value={confirmText}
              onChange={(e) => setConfirmText(e.target.value)}
              className="mt-2.5 w-full rounded-lg border border-[#f6465d]/30 bg-[var(--to-bg)] px-3 py-2 text-xs text-white font-mono placeholder:text-[var(--to-text-dim)] focus:outline-none focus:ring-1 focus:ring-[#f6465d]/50"
              placeholder="Type DISABLE"
              autoFocus
            />
          </div>
        )}

        {/* Reason input (critical only) */}
        {isCritical && (
          <div className="mb-5">
            <label className="text-[10px] uppercase tracking-wider text-[var(--to-text-dim)] mb-1.5 block">
              Reason for change
            </label>
            <input
              type="text"
              value={reason}
              onChange={(e) => setReason(e.target.value)}
              className="w-full rounded-lg border border-[var(--to-border)] bg-[var(--to-bg)] px-3 py-2 text-xs text-white placeholder:text-[var(--to-text-dim)] focus:outline-none focus:ring-1 focus:ring-indigo-500/50"
              placeholder="e.g., Testing new strategy parameters"
            />
          </div>
        )}

        {/* Actions */}
        <div className="flex items-center justify-between pt-1">
          <p className="text-[10px] text-[var(--to-text-dim)] font-mono">
            ~30s propagation
          </p>
          <div className="flex gap-2">
            <button
              onClick={onCancel}
              className="rounded-lg border border-[var(--to-border)] bg-[var(--to-surface)] px-4 py-2 text-xs text-[var(--to-text-secondary)] hover:bg-[var(--to-surface-raised)] transition-colors"
            >
              Cancel
            </button>
            <button
              onClick={() => onConfirm(reason)}
              disabled={!canConfirm}
              className={cn(
                'rounded-lg px-4 py-2 text-xs font-medium transition-all',
                action === 'disable'
                  ? 'bg-[#f6465d] text-white hover:bg-[#f6465d]/90 disabled:bg-[#f6465d]/20 disabled:text-[#f6465d]/40'
                  : 'bg-[#0ecb81] text-black hover:bg-[#0ecb81]/90 disabled:bg-[#0ecb81]/20',
              )}
            >
              {action === 'disable' ? 'Disable Guard' : 'Enable Guard'}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}

/* ═══════════════════════════════════════════════════════════
   THRESHOLD EDITOR — Inline value controls
   ═══════════════════════════════════════════════════════════ */

function ThresholdEditor({
  threshold,
  onUpdate,
  disabled,
}: {
  threshold: ThresholdConfig;
  onUpdate: (key: string, value: number | boolean) => void;
  disabled?: boolean;
}) {
  if (threshold.value_type === 'bool') {
    return (
      <div className="flex items-center justify-between py-2">
        <span className="text-[11px] text-[var(--to-text-secondary)]">
          {threshold.name}
        </span>
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
      <span className="text-[11px] text-[var(--to-text-secondary)] shrink-0">
        {threshold.name}
      </span>
      <div className="flex items-center gap-1.5">
        <input
          type="number"
          value={threshold.current_value as number}
          onChange={(e) => {
            const val =
              threshold.value_type === 'int'
                ? parseInt(e.target.value, 10)
                : parseFloat(e.target.value);
            if (!isNaN(val)) onUpdate(threshold.setting_key, val);
          }}
          min={threshold.min_value ?? undefined}
          max={threshold.max_value ?? undefined}
          step={threshold.value_type === 'int' ? 1 : 0.1}
          disabled={disabled}
          className="w-20 rounded-md border border-[var(--to-border)] bg-[var(--to-bg)] px-2 py-1 text-right text-xs text-white font-mono focus:outline-none focus:ring-1 focus:ring-indigo-500/50 disabled:opacity-40"
        />
        {threshold.unit && (
          <span className="text-[10px] text-[var(--to-text-dim)] w-8 font-mono">
            {threshold.unit}
          </span>
        )}
      </div>
    </div>
  );
}

/* ═══════════════════════════════════════════════════════════
   GUARD CARD — Glass panel with tier-aware styling
   ═══════════════════════════════════════════════════════════ */

function GuardCard({
  guard,
  onToggle,
  onThresholdUpdate,
  isUpdating,
}: {
  guard: GuardConfig;
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
      {/* Main row */}
      <div className="flex items-center gap-3 px-4 py-3">
        {/* Icon */}
        <div
          className={cn(
            'flex h-8 w-8 shrink-0 items-center justify-center rounded-lg transition-colors',
            isEnabled ? t.iconBg : 'bg-[var(--to-surface-raised)]',
          )}
        >
          <Icon className={cn('h-3.5 w-3.5', isEnabled ? t.iconColor : 'text-[var(--to-text-dim)]')} />
        </div>

        {/* Info */}
        <div className="min-w-0 flex-1">
          <div className="flex items-center gap-2">
            <span className="text-[13px] font-medium text-[var(--to-text-primary)] truncate">
              {guard.name}
            </span>
            {guard.tier === 'critical' && (
              <Lock className="h-3 w-3 shrink-0 text-[#f6465d]/60" />
            )}
            {guard.rejection_count_7d > 0 && (
              <span className={cn('shrink-0 inline-flex items-center rounded-md px-1.5 py-0.5 text-[9px] font-mono font-medium', t.badge)}>
                {guard.rejection_count_7d} blocked
              </span>
            )}
          </div>
          <div className="flex items-center gap-1.5 mt-0.5 flex-wrap">
            {guard.dynamic_threshold?.enabled ? (
              /* For guards with dynamic thresholds, show a single merged pill */
              guard.thresholds.filter((th) => th.value_type !== 'bool').map((th) => (
                <span
                  key={th.setting_key}
                  className="inline-flex items-center gap-1 rounded bg-[#7b8cff]/10 border border-[#7b8cff]/20 px-1.5 py-0.5 text-[9px] font-mono text-[#7b8cff]"
                >
                  <Zap className="h-2.5 w-2.5" />
                  <span className="text-[#7b8cff]/60">{th.name}:</span>
                  <span className="text-[var(--to-text-primary)]">{th.current_value}</span>
                  <span className="text-[#7b8cff]/40">|</span>
                  <span className="text-[#7b8cff]/60">range</span>
                  <span>{guard.dynamic_threshold.min_val}–{guard.dynamic_threshold.max_val}</span>
                </span>
              ))
            ) : guard.thresholds.length > 0 ? (
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
              <p className="text-[10px] text-[var(--to-text-dim)] truncate">
                {guard.user_description}
              </p>
            )}
          </div>
        </div>

        {/* Controls */}
        <div className="flex items-center gap-2 shrink-0">
          {guard.value_type !== 'bool' && (
            <span className="text-xs font-mono text-[var(--to-text-primary)] bg-[var(--to-surface-raised)] border border-[var(--to-border)] px-2 py-0.5 rounded-md">
              {guard.enabled}
              {guard.unit && <span className="text-[var(--to-text-dim)] ml-0.5">{guard.unit}</span>}
            </span>
          )}

          {isUpdating && <Loader2 className="h-3.5 w-3.5 animate-spin text-[#f0b90b]" />}

          {guard.value_type === 'bool' && (
            <Toggle checked={isEnabled} onChange={() => onToggle(guard)} disabled={isUpdating} />
          )}

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

      {/* Expanded panel */}
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
            <ThresholdEditor
              key={th.setting_key}
              threshold={th}
              onUpdate={(key, val) => onThresholdUpdate(guard.guard_id, key, val)}
              disabled={isUpdating}
            />
          ))}

          {guard.dynamic_threshold?.enabled && (
            <div className="mt-2 pt-2.5 border-t border-[var(--to-border-subtle)]">
              <div className="flex items-center gap-1.5 mb-2">
                <Zap className="h-3 w-3 text-[#7b8cff]" />
                <span className="text-[10px] font-medium text-[#7b8cff]">Dynamic Threshold</span>
              </div>
              <p className="text-[9px] text-[var(--to-text-dim)] leading-relaxed mb-2">
                {guard.dynamic_threshold.description}
              </p>
              <div className="grid grid-cols-3 gap-2">
                <div className="rounded bg-[var(--to-bg)] border border-[var(--to-border-subtle)] px-2 py-1.5 text-center">
                  <p className="text-[8px] text-[var(--to-text-dim)] uppercase tracking-wider">Base</p>
                  <p className="text-xs font-mono font-semibold text-[var(--to-text-primary)]">{guard.dynamic_threshold.base}</p>
                </div>
                <div className="rounded bg-[#0ecb81]/5 border border-[#0ecb81]/15 px-2 py-1.5 text-center">
                  <p className="text-[8px] text-[#0ecb81]/60 uppercase tracking-wider">Best</p>
                  <p className="text-xs font-mono font-semibold text-[#0ecb81]">{guard.dynamic_threshold.min_val}</p>
                </div>
                <div className="rounded bg-[#f6465d]/5 border border-[#f6465d]/15 px-2 py-1.5 text-center">
                  <p className="text-[8px] text-[#f6465d]/60 uppercase tracking-wider">Strictest</p>
                  <p className="text-xs font-mono font-semibold text-[#f6465d]">{guard.dynamic_threshold.max_val}</p>
                </div>
              </div>
              <div className="mt-2 space-y-0.5">
                <p className="text-[8px] text-[var(--to-text-dim)]">London/NY: -5 | Asia/Sydney: +5</p>
                <p className="text-[8px] text-[var(--to-text-dim)]">ADX&gt;30 (trending): -5 | ADX&lt;20 (choppy): +3</p>
                <p className="text-[8px] text-[var(--to-text-dim)]">RVOL&gt;1.5 (high vol): +5 | RVOL&lt;0.8 (low vol): +8</p>
              </div>
            </div>
          )}

          <div className="flex items-start gap-2 mt-2 pt-2.5 border-t border-[var(--to-border-subtle)]">
            <Info className="h-3 w-3 text-[var(--to-text-dim)] shrink-0 mt-0.5" />
            <p className="text-[10px] text-[var(--to-text-dim)] leading-relaxed">{guard.user_description}</p>
          </div>
        </div>
      )}
    </div>
  );
}

/* ═══════════════════════════════════════════════════════════
   SUMMARY KPI CARDS — Mini stat cards for top overview
   ═══════════════════════════════════════════════════════════ */

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
      <p className="text-[10px] uppercase tracking-wider text-[var(--to-text-dim)] mb-1">
        {label}
      </p>
      <p className="text-xl font-semibold font-mono" style={{ color: accent }}>
        {value}
      </p>
      {sub && (
        <p className="text-[10px] text-[var(--to-text-dim)] mt-0.5 font-mono">
          {sub}
        </p>
      )}
    </div>
  );
}

/* ═══════════════════════════════════════════════════════════
   MAIN PANEL
   ═══════════════════════════════════════════════════════════ */

export function GuardsPanel() {
  const { data, isLoading, error } = useGuardsConfig();
  const updateGuard = useUpdateGuard();
  const [confirmDialog, setConfirmDialog] = useState<{
    guard: GuardConfig;
    action: 'disable' | 'enable';
  } | null>(null);
  const [savingGuards, setSavingGuards] = useState<Set<string>>(new Set());

  const handleToggle = useCallback(
    (guard: GuardConfig) => {
      const newValue = !guard.enabled;
      const action = newValue ? 'enable' : 'disable';

      if (guard.tier === 'critical' || (guard.tier === 'important' && action === 'disable')) {
        setConfirmDialog({ guard, action });
        return;
      }

      setSavingGuards((prev) => new Set(prev).add(guard.guard_id));
      updateGuard.mutate(
        { guardId: guard.guard_id, value: newValue, change_reason: `${action}d via UI` },
        {
          onSettled: () =>
            setSavingGuards((prev) => { const n = new Set(prev); n.delete(guard.guard_id); return n; }),
        },
      );
    },
    [updateGuard],
  );

  const handleConfirm = useCallback(
    (reason: string) => {
      if (!confirmDialog) return;
      const { guard, action } = confirmDialog;
      setSavingGuards((prev) => new Set(prev).add(guard.guard_id));
      updateGuard.mutate(
        { guardId: guard.guard_id, value: action === 'enable', change_reason: reason || `${action}d via UI` },
        {
          onSettled: () =>
            setSavingGuards((prev) => { const n = new Set(prev); n.delete(guard.guard_id); return n; }),
        },
      );
      setConfirmDialog(null);
    },
    [confirmDialog, updateGuard],
  );

  const handleThresholdUpdate = useCallback(
    (guardId: string, key: string, value: number | boolean) => {
      if (key === '__primary__') {
        setSavingGuards((prev) => new Set(prev).add(guardId));
        updateGuard.mutate(
          { guardId, value, change_reason: 'Threshold updated via UI' },
          {
            onSettled: () =>
              setSavingGuards((prev) => { const n = new Set(prev); n.delete(guardId); return n; }),
          },
        );
        return;
      }
      const guard = Object.values(data?.groups || {}).flat().find((g) => g.guard_id === guardId);
      if (!guard) return;
      setSavingGuards((prev) => new Set(prev).add(guardId));
      updateGuard.mutate(
        { guardId, value: guard.enabled, thresholds: { [key]: value }, change_reason: `Threshold ${key} updated via UI` },
        {
          onSettled: () =>
            setSavingGuards((prev) => { const n = new Set(prev); n.delete(guardId); return n; }),
        },
      );
    },
    [data, updateGuard],
  );

  /* Loading state */
  if (isLoading) {
    return (
      <div className="flex items-center justify-center py-16">
        <Loader2 className="h-5 w-5 animate-spin text-[var(--to-text-dim)]" />
        <span className="ml-2.5 text-sm text-[var(--to-text-dim)]">Loading guards...</span>
      </div>
    );
  }

  /* Error state */
  if (error) {
    return (
      <div className="to-panel p-5 border-[#f6465d]/30">
        <div className="flex items-center gap-2 mb-2">
          <ShieldX className="h-4 w-4 text-[#f6465d]" />
          <p className="text-sm font-medium text-[#f6465d]">Failed to load guards</p>
        </div>
        <p className="text-xs text-[var(--to-text-dim)]">Check your API connection and try refreshing.</p>
      </div>
    );
  }

  if (!data) return null;

  const { groups, group_labels, total_rejections_7d, total_signals_7d } = data;
  const allGuards = Object.values(groups).flat();
  const enabledCount = allGuards.filter((g) => g.value_type !== 'bool' || g.enabled).length;
  const criticalCount = allGuards.filter((g) => g.tier === 'critical').length;
  const rejectionPct = total_signals_7d > 0 ? ((total_rejections_7d / total_signals_7d) * 100).toFixed(1) : '0';

  return (
    <div className="space-y-6">
      {/* KPI row */}
      <div className="flex gap-3 flex-wrap">
        <KpiCard
          label="Active Guards"
          value={enabledCount}
          sub={`of ${allGuards.length} total`}
          accent="#0ecb81"
        />
        <KpiCard
          label="Critical Guards"
          value={criticalCount}
          sub="always recommended"
          accent="#f6465d"
        />
        <KpiCard
          label="Signals Blocked (7d)"
          value={total_rejections_7d}
          sub={total_signals_7d > 0 ? `${rejectionPct}% of ${total_signals_7d} signals` : 'no signals yet'}
          accent="#f0b90b"
        />
      </div>

      {/* Guard groups */}
      {GROUP_ORDER.map((groupKey) => {
        const guards = groups[groupKey];
        if (!guards || guards.length === 0) return null;
        const label = group_labels[groupKey] || groupKey;
        const GroupIcon = GROUP_ICONS[groupKey] ?? Shield;

        return (
          <div key={groupKey} className="to-panel overflow-hidden">
            {/* Group header */}
            <div className="to-panel-header">
              <div className="flex items-center gap-2">
                <GroupIcon className="h-3.5 w-3.5 text-[var(--to-text-dim)]" />
                <span className="to-panel-title">{label}</span>
                <span className="text-[10px] font-mono text-[var(--to-text-dim)] bg-[var(--to-surface-raised)] px-1.5 py-0.5 rounded">
                  {guards.length}
                </span>
              </div>
            </div>

            {/* Guard list */}
            <div className="p-3 space-y-2">
              {guards.map((guard) => (
                <GuardCard
                  key={guard.guard_id}
                  guard={guard}
                  onToggle={handleToggle}
                  onThresholdUpdate={handleThresholdUpdate}
                  isUpdating={savingGuards.has(guard.guard_id)}
                />
              ))}
            </div>
          </div>
        );
      })}

      {/* Confirmation dialog */}
      {confirmDialog && (
        <ConfirmDialog
          guard={confirmDialog.guard}
          action={confirmDialog.action}
          onConfirm={handleConfirm}
          onCancel={() => setConfirmDialog(null)}
        />
      )}
    </div>
  );
}
