'use client';

import { cn } from '@/lib/utils';
import { Cog, Eye, EyeOff } from 'lucide-react';
import { useState } from 'react';

interface ConfigItem {
  key: string;
  value: string;
  sensitive?: boolean;
  /**
   * Mark critical envs (API URLs, keys) for stronger danger styling when missing.
   */
  critical?: boolean;
}

interface ConfigDisplayProps {
  title: string;
  items: ConfigItem[];
}

export function ConfigDisplay({ title, items }: ConfigDisplayProps) {
  const [showSensitive, setShowSensitive] = useState(false);

  return (
    <div className="to-panel">
      <div className="to-panel-header flex items-center justify-between">
        <div className="flex items-center gap-2">
          <Cog className="w-4 h-4 text-text-dim" />
          <span className="font-mono text-[11px] uppercase tracking-[0.18em] text-text-muted">
            {title}
          </span>
        </div>
        {items.some((i) => i.sensitive) && (
          <button
            onClick={() => setShowSensitive(!showSensitive)}
            className="flex items-center gap-1.5 text-[10px] font-mono text-text-muted hover:text-text-secondary transition-colors"
          >
            {showSensitive ? <EyeOff className="w-3 h-3" /> : <Eye className="w-3 h-3" />}
            {showSensitive ? 'Hide' : 'Show'}
          </button>
        )}
      </div>
      <div className="divide-y divide-panel-border-subtle">
        {items.map((item) => {
          const isMissing = !item.value;
          const tone = isMissing
            ? item.critical
              ? 'bg-[var(--to-short)]/8 border-l-2 border-[var(--to-short)]/50'
              : 'bg-amber-500/5 border-l-2 border-amber-500/40'
            : '';

          return (
            <div
              key={item.key}
              className={cn(
                'px-4 py-2.5 flex items-center justify-between',
                tone,
              )}
            >
              <span className="text-[11px] text-text-muted uppercase tracking-wider font-mono">
                {item.key}
              </span>
              <span
                className={cn(
                  'font-mono text-xs',
                  item.value ? 'text-text-secondary' : 'text-text-dim',
                )}
              >
                {item.sensitive && !showSensitive
                  ? item.value
                    ? `${item.value.slice(0, 8)}${'*'.repeat(
                        Math.max(0, item.value.length - 8),
                      )}`
                    : 'Not set'
                  : item.value || 'Not set'}
              </span>
            </div>
          );
        })}
      </div>
    </div>
  );
}
