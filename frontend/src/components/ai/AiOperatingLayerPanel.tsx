import type { AiOperatingLayerRun } from '@/lib/aiRuns';
import { Badge } from '@/components/ui/badge';
import { cn } from '@/lib/utils';

export function AiOperatingLayerPanel({
  run,
}: {
  run: AiOperatingLayerRun;
}) {
  const chartStatus = run.moduleStatus.chartContext;
  const statusTone =
    chartStatus.status === 'ok'
      ? 'bg-[var(--to-long)]/20 text-[var(--to-long)]'
      : chartStatus.status === 'degraded'
      ? 'bg-amber-500/20 text-amber-400'
      : 'bg-muted text-muted-foreground';

  return (
    <section className='rounded-lg border border-border bg-card overflow-hidden'>
      <div className='px-4 py-2.5 border-b border-border flex items-center justify-between gap-2'>
        <span className='text-[11px] text-muted-foreground uppercase tracking-wider'>
          AI Operating Layer
        </span>
        <Badge className='text-[10px] px-2 py-0.5 border-0 bg-muted text-muted-foreground'>
          {run.analysisMode}
        </Badge>
      </div>

      <div className='p-4 space-y-4'>
        <div className='space-y-1'>
          <div className='text-[11px] text-muted-foreground uppercase tracking-wider'>
            Verdict
          </div>
          <div className='flex items-center justify-between gap-3'>
            <p className='text-sm text-foreground/90'>{run.layeredOutput.topLevel.verdict}</p>
            <span className='font-mono text-xs text-muted-foreground'>
              Confidence: {run.layeredOutput.topLevel.confidence}
            </span>
          </div>
        </div>

        <div className='space-y-2'>
          <div className='flex items-center justify-between gap-3'>
            <span className='text-[11px] text-muted-foreground uppercase tracking-wider'>
              Chart Context
            </span>
            <span
              className={cn(
                'rounded px-2 py-1 text-[10px] font-semibold uppercase',
                statusTone
              )}
            >
              {chartStatus.status}
            </span>
          </div>
          {chartStatus.reason ? (
            <p className='text-xs text-muted-foreground'>{chartStatus.reason}</p>
          ) : null}
        </div>

        {Object.keys(run.pineContext || {}).length > 0 ? (
          <div className='space-y-1'>
            <div className='text-[11px] text-muted-foreground uppercase tracking-wider'>
              Pine Context
            </div>
            <p className='text-xs text-foreground/90'>
              {typeof run.pineContext.script_name === 'string'
                ? run.pineContext.script_name
                : 'Available'}
            </p>
          </div>
        ) : null}
      </div>
    </section>
  );
}
