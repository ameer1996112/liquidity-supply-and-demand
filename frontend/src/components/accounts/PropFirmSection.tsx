'use client';

import { usePropFirmChallenge } from '@/hooks/usePropFirmChallenge';
import { Skeleton } from '@/components/ui/skeleton';
import { ProgressBars } from '../prop-firm/ProgressBars';
import { WarningBanner } from '../prop-firm/WarningBanner';

export function PropFirmSection({ accountName, serverName }: { accountName: string; serverName?: string }) {
  const { data, isLoading, error } = usePropFirmChallenge(accountName);

  if (isLoading) {
    return <div className="p-4"><Skeleton className="h-16 w-full rounded-md" /></div>;
  }

  if (error || !data) return null;

  if (!data.firm_detected) {
    // UI-04: Unknown firm fallback
    return (
      <div className="p-3 mx-4 mb-4 rounded border border-[#2a2e39] bg-[#1e222d]/30 flex items-center justify-between">
        <span className="text-[10px] font-mono text-[var(--to-text-dim)]">Prop Firm Status</span>
        <span className="text-[10px] font-mono text-[var(--to-text-dim)]">Unknown Firm ({serverName || 'N/A'})</span>
      </div>
    );
  }

  const safeMetrics = data.metrics || ({} as any);

  return (
    <div className="p-4 mx-4 mb-4 rounded border border-[#2a2e39] bg-[#1e222d]/40">
      <div className="flex justify-between items-center mb-3">
        <span className="text-[11px] font-mono font-bold text-[var(--to-text-secondary)]">
          {data.firm_info?.firm_display_name || 'Prop Firm Challenge'}
          <span className="ml-2 px-1.5 py-0.5 rounded text-[9px] bg-[#2a2e39] text-[var(--to-text-dim)] font-medium">
            {data.firm_info?.challenge_type?.toUpperCase().replace('_', ' ')}
          </span>
        </span>
        {safeMetrics.days_remaining != null && (
          <span className="text-[10px] font-mono text-[var(--to-text-dim)] flex items-center gap-1">
             {safeMetrics.days_remaining} Days Left
          </span>
        )}
      </div>

      <WarningBanner metrics={safeMetrics} limits={data.firm_info!} />
      <ProgressBars metrics={safeMetrics} limits={data.firm_info!} />
    </div>
  );
}
