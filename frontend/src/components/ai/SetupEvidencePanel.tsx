import { Badge } from '@/components/ui/badge';

type SetupEvidencePanelProps = {
  evidence: {
    status: string;
    focusZone: Record<string, unknown> | null;
    focusImage: {
      path?: string | null;
      url?: string | null;
      region?: string | null;
    } | null;
    reason: string;
  };
  zones: Array<Record<string, unknown>>;
  pineLabels: Array<Record<string, unknown>>;
};

function renderZoneSummary(zone: Record<string, unknown> | null): string {
  if (!zone) return 'No focus zone detected';

  const label =
    typeof zone.label === 'string' && zone.label.trim()
      ? zone.label
      : 'Primary zone';
  const high =
    typeof zone.high === 'number'
      ? zone.high.toFixed(4)
      : typeof zone.price === 'number'
      ? zone.price.toFixed(4)
      : null;
  const low = typeof zone.low === 'number' ? zone.low.toFixed(4) : null;

  if (high && low) return `${label}: ${low} - ${high}`;
  if (high) return `${label}: ${high}`;
  return label;
}

function renderLabelSnippet(
  pineLabels: Array<Record<string, unknown>>
): string {
  const firstLabel = pineLabels.find(
    (item) => typeof item.label === 'string' && item.label.trim()
  );
  if (!firstLabel || typeof firstLabel.label !== 'string') {
    return 'No Pine labels captured';
  }

  return firstLabel.label.split('\n')[0] ?? firstLabel.label;
}

export function SetupEvidencePanel({
  evidence,
  zones,
  pineLabels,
}: SetupEvidencePanelProps) {
  const imageUrl = evidence.focusImage?.url ?? null;
  const zoneSummary = renderZoneSummary(evidence.focusZone);
  const zoneCount = zones.length;
  const labelSnippet = renderLabelSnippet(pineLabels);

  return (
    <div className='space-y-3 rounded-lg border border-border/80 bg-background/40 p-3'>
      <div className='flex items-center justify-between gap-3'>
        <span className='text-[11px] text-muted-foreground uppercase tracking-wider'>
          Setup Evidence
        </span>
        <Badge className='text-[10px] px-2 py-0.5 border-0 bg-muted text-muted-foreground'>
          {evidence.status}
        </Badge>
      </div>

      {imageUrl ? (
        <img
          src={imageUrl}
          alt='Focused setup'
          className='w-full rounded-md border border-border object-cover'
        />
      ) : (
        <p className='text-xs text-muted-foreground'>{evidence.reason}</p>
      )}

      <div className='grid gap-2 sm:grid-cols-2'>
        <div className='space-y-1'>
          <div className='text-[11px] text-muted-foreground uppercase tracking-wider'>
            Focus Zone
          </div>
          <p className='text-xs text-foreground/90'>{zoneSummary}</p>
        </div>
        <div className='space-y-1'>
          <div className='text-[11px] text-muted-foreground uppercase tracking-wider'>
            Pine Snapshot
          </div>
          <p className='text-xs text-foreground/90'>{labelSnippet}</p>
          <p className='text-[11px] text-muted-foreground'>
            Zones captured: {zoneCount}
          </p>
        </div>
      </div>
    </div>
  );
}
