'use client';

import { useState, useCallback } from 'react';
import { cn } from '@/lib/utils';
import {
  useGuardsConfig,
  useUpdateGuard,
  type GuardConfig,
  type ThresholdConfig,
} from '@/hooks/useGuards';
import {
  Shield,
  ShieldAlert,
  ShieldCheck,
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
} from 'lucide-react';

// ── Tier Colors & Icons ────────────────────────────────

const TIER_STYLES: Record<
  string,
  { border: string; bg: string; icon: string; badge: string }
> = {
  critical: {
    border: 'border-red-500/30',
    bg: 'bg-red-500/5',
    icon: 'text-red-400',
    badge: 'bg-red-500/20 text-red-300',
  },
  important: {
    border: 'border-amber-500/30',
    bg: 'bg-amber-500/5',
    icon: 'text-amber-400',
    badge: 'bg-amber-500/20 text-amber-300',
  },
  convenience: {
    border: 'border-emerald-500/30',
    bg: 'bg-emerald-500/5',
    icon: 'text-emerald-400',
    badge: 'bg-emerald-500/20 text-emerald-300',
  },
};

const GUARD_ICONS: Record<
  string,
  React.ComponentType<{ className?: string }>
> = {
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

// ── Toggle Switch ──────────────────────────────────────

function ToggleSwitch({
  checked,
  onChange,
  disabled,
}: {
  checked: boolean;
  onChange: (checked: boolean) => void;
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
        'relative inline-flex h-6 w-10 shrink-0 rounded-full border border-transparent transition-colors',
        'focus:outline-none focus-visible:ring-2 focus-visible:ring-emerald-500 focus-visible:ring-offset-2 focus-visible:ring-offset-[#131722]',
        checked ? 'bg-emerald-500' : 'bg-[#2a2e39]',
        disabled && 'opacity-50 cursor-not-allowed'
      )}
    >
      <span
        className={cn(
          'pointer-events-none inline-block h-5 w-5 rounded-full bg-white shadow ring-0 transition',
          checked ? 'translate-x-4' : 'translate-x-0.5'
        )}
      />
    </button>
  );
}

// ── Confirmation Dialog ────────────────────────────────

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
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm">
      <div className="w-full max-w-md rounded-xl border border-[#2a2e39] bg-[#1a1e2e] p-6 shadow-2xl">
        <div className="flex items-center gap-3 mb-4">
          <div
            className={cn(
              'flex h-10 w-10 items-center justify-center rounded-lg',
              action === 'disable' ? 'bg-red-500/20' : 'bg-emerald-500/20'
            )}
          >
            {action === 'disable' ? (
              <AlertTriangle className="h-5 w-5 text-red-400" />
            ) : (
              <ShieldCheck className="h-5 w-5 text-emerald-400" />
            )}
          </div>
          <div>
            <h3 className="text-sm font-semibold text-white">
              {action === 'disable' ? 'Disable' : 'Enable'} {guard.name}?
            </h3>
            <p className="text-xs text-[var(--to-text-dim)]">
              {guard.tier === 'critical' ? 'Critical guard' : 'Important guard'}
            </p>
          </div>
        </div>

        <p className="mb-4 text-xs text-[var(--to-text-dim)] leading-relaxed">
          {action === 'disable'
            ? guard.user_description
            : `Re-enabling "${guard.name}" will restore this protection.`}
        </p>

        {isCritical && action === 'disable' && (
          <div className="mb-4 rounded-lg border border-red-500/30 bg-red-500/10 p-3">
            <p className="text-xs text-red-300 mb-2">
              This is a capital protection guard. Disabling it may expose your
              account to significant risk.
            </p>
            <p className="text-xs text-red-300 font-medium">
              Type <span className="font-mono bg-red-500/20 px-1 rounded">DISABLE</span> to confirm:
            </p>
            <input
              type="text"
              value={confirmText}
              onChange={(e) => setConfirmText(e.target.value)}
              className="mt-2 w-full rounded-md border border-red-500/30 bg-[#131722] px-3 py-2 text-xs text-white font-mono placeholder:text-[var(--to-text-dim)] focus:outline-none focus:ring-1 focus:ring-red-500"
              placeholder="Type DISABLE"
              autoFocus
            />
          </div>
        )}

        {isCritical && (
          <div className="mb-4">
            <label className="text-xs text-[var(--to-text-dim)] mb-1 block">
              Reason for change:
            </label>
            <input
              type="text"
              value={reason}
              onChange={(e) => setReason(e.target.value)}
              className="w-full rounded-md border border-[#2a2e39] bg-[#131722] px-3 py-2 text-xs text-white placeholder:text-[var(--to-text-dim)] focus:outline-none focus:ring-1 focus:ring-indigo-500"
              placeholder="e.g., Testing new strategy parameters"
            />
          </div>
        )}

        <div className="flex items-center justify-between">
          <p className="text-[10px] text-[var(--to-text-dim)]">
            Changes apply within ~30 seconds
          </p>
          <div className="flex gap-2">
            <button
              onClick={onCancel}
              className="rounded-md border border-[#2a2e39] bg-[#1e222d] px-4 py-2 text-xs text-[var(--to-text-dim)] hover:bg-[#2a2e39] transition-colors"
            >
              Cancel
            </button>
            <button
              onClick={() => onConfirm(reason)}
              disabled={!canConfirm}
              className={cn(
                'rounded-md px-4 py-2 text-xs font-medium transition-colors',
                action === 'disable'
                  ? 'bg-red-600 text-white hover:bg-red-700 disabled:bg-red-600/30 disabled:text-red-300/50'
                  : 'bg-emerald-600 text-white hover:bg-emerald-700 disabled:bg-emerald-600/30'
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

// ── Threshold Editor ───────────────────────────────────

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
      <div className="flex items-center justify-between py-1.5">
        <span className="text-[11px] text-[var(--to-text-dim)]">
          {threshold.name}
        </span>
        <ToggleSwitch
          checked={Boolean(threshold.current_value)}
          onChange={(v) => onUpdate(threshold.setting_key, v)}
          disabled={disabled}
        />
      </div>
    );
  }

  return (
    <div className="flex items-center justify-between gap-3 py-1.5">
      <span className="text-[11px] text-[var(--to-text-dim)] shrink-0">
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
          className="w-20 rounded border border-[#2a2e39] bg-[#131722] px-2 py-1 text-right text-xs text-white font-mono focus:outline-none focus:ring-1 focus:ring-indigo-500 disabled:opacity-50"
        />
        {threshold.unit && (
          <span className="text-[10px] text-[var(--to-text-dim)] w-8">
            {threshold.unit}
          </span>
        )}
      </div>
    </div>
  );
}

// ── Guard Card ─────────────────────────────────────────

function GuardCard({
  guard,
  onToggle,
  onThresholdUpdate,
  isUpdating,
}: {
  guard: GuardConfig;
  onToggle: (guard: GuardConfig) => void;
  onThresholdUpdate: (
    guardId: string,
    thresholdKey: string,
    value: number | boolean
  ) => void;
  isUpdating: boolean;
}) {
  const [expanded, setExpanded] = useState(false);
  const tier = TIER_STYLES[guard.tier] || TIER_STYLES.convenience;
  const Icon = GUARD_ICONS[guard.guard_id] || Shield;
  const isEnabled =
    guard.value_type === 'bool' ? Boolean(guard.enabled) : true;
  const hasThresholds = guard.thresholds.length > 0;
  const isExpandable =
    hasThresholds || guard.value_type !== 'bool';

  return (
    <div
      className={cn(
        'rounded-lg border transition-all',
        tier.border,
        isEnabled ? tier.bg : 'bg-[#1a1e2e]/50 opacity-70',
        'hover:border-opacity-60'
      )}
    >
      {/* Main row */}
      <div className="flex items-center justify-between gap-3 px-4 py-3">
        <div className="flex items-center gap-3 min-w-0 flex-1">
          {/* Icon */}
          <div
            className={cn(
              'flex h-9 w-9 shrink-0 items-center justify-center rounded-lg',
              isEnabled ? 'bg-[#2a2e39]' : 'bg-[#1e222d]'
            )}
          >
            <Icon
              className={cn('h-4 w-4', isEnabled ? tier.icon : 'text-gray-600')}
            />
          </div>

          {/* Info */}
          <div className="min-w-0 flex-1">
            <div className="flex items-center gap-2">
              <p className="text-sm font-medium text-[var(--to-text-primary)]">
                {guard.name}
              </p>
              {guard.tier === 'critical' && (
                <Lock className="h-3 w-3 text-red-400" />
              )}
              {/* Rejection badge */}
              {guard.rejection_count_7d > 0 && (
                <span
                  className={cn(
                    'inline-flex items-center rounded-full px-1.5 py-0.5 text-[10px] font-mono font-medium',
                    tier.badge
                  )}
                >
                  {guard.rejection_count_7d} blocked
                </span>
              )}
            </div>
            <p className="text-[11px] text-[var(--to-text-dim)] line-clamp-1">
              {guard.user_description}
            </p>
          </div>
        </div>

        {/* Controls */}
        <div className="flex items-center gap-2 shrink-0">
          {/* Numeric value display */}
          {guard.value_type !== 'bool' && (
            <span className="text-xs font-mono text-[var(--to-text-primary)] bg-[#2a2e39] px-2 py-1 rounded">
              {guard.enabled}
              {guard.unit && (
                <span className="text-[var(--to-text-dim)] ml-0.5">
                  {guard.unit}
                </span>
              )}
            </span>
          )}

          {isUpdating && (
            <span className="text-[10px] font-mono text-amber-500">
              Saving...
            </span>
          )}

          {guard.value_type === 'bool' && (
            <ToggleSwitch
              checked={isEnabled}
              onChange={() => onToggle(guard)}
              disabled={isUpdating}
            />
          )}

          {isExpandable && (
            <button
              onClick={() => setExpanded(!expanded)}
              className="flex h-7 w-7 items-center justify-center rounded-md text-[var(--to-text-dim)] hover:bg-[#2a2e39] transition-colors"
            >
              {expanded ? (
                <ChevronDown className="h-4 w-4" />
              ) : (
                <ChevronRight className="h-4 w-4" />
              )}
            </button>
          )}
        </div>
      </div>

      {/* Expanded section */}
      {expanded && (
        <div className="border-t border-[#2a2e39]/50 px-4 py-3 space-y-1">
          {/* Numeric primary value editor */}
          {guard.value_type !== 'bool' && (
            <div className="flex items-center justify-between gap-3 py-1.5 mb-2 border-b border-[#2a2e39]/30 pb-3">
              <span className="text-[11px] text-[var(--to-text-primary)] font-medium">
                {guard.name}
              </span>
              <div className="flex items-center gap-1.5">
                <input
                  type="number"
                  value={guard.enabled as number}
                  onChange={(e) => {
                    const val =
                      guard.value_type === 'int'
                        ? parseInt(e.target.value, 10)
                        : parseFloat(e.target.value);
                    if (!isNaN(val)) {
                      onThresholdUpdate(guard.guard_id, '__primary__', val);
                    }
                  }}
                  min={guard.min_value ?? undefined}
                  max={guard.max_value ?? undefined}
                  step={guard.value_type === 'int' ? 1 : 0.1}
                  disabled={isUpdating}
                  className="w-20 rounded border border-[#2a2e39] bg-[#131722] px-2 py-1 text-right text-xs text-white font-mono focus:outline-none focus:ring-1 focus:ring-indigo-500 disabled:opacity-50"
                />
                {guard.unit && (
                  <span className="text-[10px] text-[var(--to-text-dim)] w-8">
                    {guard.unit}
                  </span>
                )}
              </div>
            </div>
          )}

          {/* Threshold editors */}
          {guard.thresholds.map((t) => (
            <ThresholdEditor
              key={t.setting_key}
              threshold={t}
              onUpdate={(key, val) =>
                onThresholdUpdate(guard.guard_id, key, val)
              }
              disabled={isUpdating}
            />
          ))}

          {/* Info tooltip */}
          <div className="flex items-start gap-2 mt-2 pt-2 border-t border-[#2a2e39]/30">
            <Info className="h-3.5 w-3.5 text-[var(--to-text-dim)] shrink-0 mt-0.5" />
            <p className="text-[10px] text-[var(--to-text-dim)] leading-relaxed">
              {guard.user_description}
            </p>
          </div>
        </div>
      )}
    </div>
  );
}

// ── Main Panel ─────────────────────────────────────────

export function GuardsPanel() {
  const { data, isLoading, error } = useGuardsConfig();
  const updateGuard = useUpdateGuard();
  const [confirmDialog, setConfirmDialog] = useState<{
    guard: GuardConfig;
    action: 'disable' | 'enable';
  } | null>(null);
  const [pendingThresholds, setPendingThresholds] = useState<
    Record<string, Record<string, number | boolean>>
  >({});
  const [savingGuards, setSavingGuards] = useState<Set<string>>(new Set());

  // Handle boolean toggle (with confirmation for critical/important)
  const handleToggle = useCallback(
    (guard: GuardConfig) => {
      const newValue = !guard.enabled;
      const action = newValue ? 'enable' : 'disable';

      // Critical guards always need confirmation
      if (guard.tier === 'critical') {
        setConfirmDialog({ guard, action });
        return;
      }

      // Important guards need confirmation only when disabling
      if (guard.tier === 'important' && action === 'disable') {
        setConfirmDialog({ guard, action });
        return;
      }

      // Convenience guards toggle freely
      setSavingGuards((prev) => new Set(prev).add(guard.guard_id));
      updateGuard.mutate(
        {
          guardId: guard.guard_id,
          value: newValue,
          change_reason: `${action}d via UI`,
        },
        {
          onSettled: () => {
            setSavingGuards((prev) => {
              const next = new Set(prev);
              next.delete(guard.guard_id);
              return next;
            });
          },
        }
      );
    },
    [updateGuard]
  );

  // Handle confirmation dialog result
  const handleConfirm = useCallback(
    (reason: string) => {
      if (!confirmDialog) return;
      const { guard, action } = confirmDialog;
      const newValue = action === 'enable';

      setSavingGuards((prev) => new Set(prev).add(guard.guard_id));
      updateGuard.mutate(
        {
          guardId: guard.guard_id,
          value: newValue,
          change_reason: reason || `${action}d via UI`,
        },
        {
          onSettled: () => {
            setSavingGuards((prev) => {
              const next = new Set(prev);
              next.delete(guard.guard_id);
              return next;
            });
          },
        }
      );
      setConfirmDialog(null);
    },
    [confirmDialog, updateGuard]
  );

  // Handle threshold updates (debounced save)
  const handleThresholdUpdate = useCallback(
    (guardId: string, thresholdKey: string, value: number | boolean) => {
      // For primary value changes
      if (thresholdKey === '__primary__') {
        setSavingGuards((prev) => new Set(prev).add(guardId));
        updateGuard.mutate(
          {
            guardId,
            value,
            change_reason: 'Threshold updated via UI',
          },
          {
            onSettled: () => {
              setSavingGuards((prev) => {
                const next = new Set(prev);
                next.delete(guardId);
                return next;
              });
            },
          }
        );
        return;
      }

      // For sub-threshold changes
      const guard = Object.values(data?.groups || {})
        .flat()
        .find((g) => g.guard_id === guardId);
      if (!guard) return;

      setSavingGuards((prev) => new Set(prev).add(guardId));
      updateGuard.mutate(
        {
          guardId,
          value: guard.enabled,
          thresholds: { [thresholdKey]: value },
          change_reason: `Threshold ${thresholdKey} updated via UI`,
        },
        {
          onSettled: () => {
            setSavingGuards((prev) => {
              const next = new Set(prev);
              next.delete(guardId);
              return next;
            });
          },
        }
      );
    },
    [data, updateGuard]
  );

  if (isLoading) {
    return (
      <div className="flex items-center justify-center py-12">
        <div className="flex items-center gap-3 text-[var(--to-text-dim)]">
          <div className="h-4 w-4 animate-spin rounded-full border-2 border-indigo-500 border-t-transparent" />
          <span className="text-sm">Loading guards...</span>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="rounded-lg border border-red-500/30 bg-red-500/10 p-4">
        <p className="text-sm text-red-300">
          Failed to load guard configuration. Check your API connection.
        </p>
      </div>
    );
  }

  if (!data) return null;

  const { groups, group_labels, total_rejections_7d, total_signals_7d } = data;
  const rejectionPct =
    total_signals_7d > 0
      ? ((total_rejections_7d / total_signals_7d) * 100).toFixed(1)
      : '0';

  return (
    <div className="space-y-6">
      {/* Summary bar */}
      <div className="flex items-center gap-4 rounded-lg border border-[#2a2e39] bg-[#1e222d]/50 px-4 py-3">
        <Shield className="h-5 w-5 text-indigo-400" />
        <div className="flex-1">
          <p className="text-sm font-medium text-[var(--to-text-primary)]">
            {Object.values(groups).flat().length} Guards Active
          </p>
          <p className="text-[11px] text-[var(--to-text-dim)]">
            {total_rejections_7d} signals blocked in the last 7 days
            {total_signals_7d > 0 && ` (${rejectionPct}% of ${total_signals_7d} total)`}
          </p>
        </div>
        <div className="text-[10px] text-[var(--to-text-dim)] bg-[#2a2e39] px-2 py-1 rounded font-mono">
          ~30s propagation delay
        </div>
      </div>

      {/* Guard groups */}
      {GROUP_ORDER.map((groupKey) => {
        const guards = groups[groupKey];
        if (!guards || guards.length === 0) return null;
        const label = group_labels[groupKey] || groupKey;

        return (
          <div key={groupKey}>
            <h3 className="text-xs font-semibold text-[var(--to-text-dim)] uppercase tracking-wider mb-3">
              {label}
            </h3>
            <div className="space-y-2">
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
