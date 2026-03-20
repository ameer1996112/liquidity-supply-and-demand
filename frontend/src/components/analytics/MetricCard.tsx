'use client';

import { cn } from '@/lib/utils';

interface MetricCardProps {
  label: string;
  value: string | number;
  icon: React.ReactNode;
  trend?: 'up' | 'down';
  subtitle?: string;
}

export function MetricCard({ label, value, icon, trend, subtitle }: MetricCardProps) {
  return (
    <div className="glow-card p-4">
      <div className="flex items-start justify-between mb-2">
        <div className="flex items-center justify-center w-8 h-8 rounded bg-[#2a2e39] text-[var(--to-text-dim)]">
          {icon}
        </div>
      </div>
      <div className="space-y-1">
        <span className="text-[10px] uppercase tracking-wider text-[var(--to-text-dim)] font-medium">
          {label}
        </span>
        <div
          className={cn(
            'font-mono text-2xl font-bold tabular-nums',
            trend === 'up' && 'text-[#26a69a]',
            trend === 'down' && 'text-[#ef5350]',
            !trend && 'text-[var(--to-text-primary)]'
          )}
        >
          {value}
        </div>
        {subtitle && (
          <span className="text-[10px] text-[var(--to-text-dim)]">{subtitle}</span>
        )}
      </div>
    </div>
  );
}
