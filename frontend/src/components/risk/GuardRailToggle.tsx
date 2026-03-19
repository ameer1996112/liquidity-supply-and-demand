'use client';

import { useCallback } from 'react';
import { cn } from '@/lib/utils';
import { Shield, Newspaper, Calendar } from 'lucide-react';

export interface GuardRailItem {
  id: string;
  label: string;
  description?: string;
  enabled: boolean;
  /** If not set, toggle is read-only (e.g. coming soon) */
  settingKey?: string;
}

export interface GuardRailToggleProps {
  items: GuardRailItem[];
  onToggle: (id: string, enabled: boolean, settingKey?: string) => void;
  disabled?: boolean;
  isUpdating?: boolean;
  className?: string;
}

const ICONS: Record<string, React.ComponentType<{ className?: string }>> = {
  max_drawdown: Shield,
  news_filter: Newspaper,
  weekend_protection: Calendar,
};

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

export function GuardRailToggle({
  items,
  onToggle,
  disabled = false,
  isUpdating = false,
  className,
}: GuardRailToggleProps) {
  const handleToggle = useCallback(
    (id: string, enabled: boolean, settingKey?: string) => {
      if (settingKey) onToggle(id, enabled, settingKey);
    },
    [onToggle]
  );

  return (
    <div className={cn('space-y-3', className)}>
      {items.map((item) => {
        const Icon = ICONS[item.id] ?? Shield;
        const canEdit = !!item.settingKey;

        return (
          <div
            key={item.id}
            className={cn(
              'flex items-center justify-between gap-4 rounded-lg border border-[#2a2e39] bg-[#1e222d]/50 px-4 py-3',
              !canEdit && 'opacity-80'
            )}
          >
            <div className="flex items-center gap-3 min-w-0">
              <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-md bg-[#2a2e39] text-[var(--to-text-dim)]">
                <Icon className="h-4 w-4" />
              </div>
              <div className="min-w-0">
                <p className="text-sm font-medium text-[var(--to-text-primary)]">{item.label}</p>
                {item.description && (
                  <p className="text-[11px] text-[var(--to-text-dim)] truncate">
                    {item.description}
                  </p>
                )}
              </div>
            </div>
            <div className="flex items-center gap-2 shrink-0">
              {isUpdating && (
                <span className="text-[10px] font-mono text-amber-500">
                  Saving…
                </span>
              )}
              <ToggleSwitch
                checked={item.enabled}
                onChange={(enabled) =>
                  handleToggle(item.id, enabled, item.settingKey)
                }
                disabled={disabled || isUpdating || !canEdit}
              />
            </div>
          </div>
        );
      })}
    </div>
  );
}
