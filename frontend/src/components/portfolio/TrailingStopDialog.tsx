'use client';

import { useState, useEffect } from 'react';
import {
  Sheet,
  SheetContent,
  SheetHeader,
  SheetTitle,
  SheetFooter,
} from '@/components/ui/sheet';
import { Button } from '@/components/ui/button';
import { useAddTrailingStop } from '@/hooks/useOptimizer';
import type { ActivePosition } from '@/hooks/usePositions';
import { Loader2 } from 'lucide-react';

const MIN_PIPS = 5;
const MAX_PIPS = 200;
const DEFAULT_PIPS = 50;

export function TrailingStopDialog({
  open,
  onOpenChange,
  signalId: initialSignalId,
  positions = [],
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  signalId?: number | null;
  positions?: ActivePosition[];
}) {
  const [signalId, setSignalId] = useState<number>(initialSignalId ?? 0);
  const [trailPips, setTrailPips] = useState(DEFAULT_PIPS);
  const [waitForBreakeven, setWaitForBreakeven] = useState(true);
  const addTrailing = useAddTrailingStop();

  useEffect(() => {
    if (open) {
      setSignalId(initialSignalId ?? (positions[0]?.id ?? 0));
      setTrailPips(DEFAULT_PIPS);
      setWaitForBreakeven(true);
    }
  }, [open, initialSignalId, positions]);

  const handleSubmit = () => {
    if (!signalId) return;
    addTrailing.mutate(
      {
        signal_id: signalId,
        trail_distance_pips: trailPips,
        wait_for_breakeven: waitForBreakeven,
      },
      {
        onSuccess: () => onOpenChange(false),
      }
    );
  };

  const selectedPosition = positions.find((p) => p.id === signalId);

  return (
    <Sheet open={open} onOpenChange={onOpenChange}>
      <SheetContent className="bg-[#131722] border-l border-[#2a2e39] sm:max-w-sm">
        <SheetHeader>
          <SheetTitle className="font-mono text-sm text-zinc-200">
            Attach trailing stop
          </SheetTitle>
        </SheetHeader>

        <div className="flex flex-col gap-4 px-4 py-2">
          <div className="space-y-1.5">
            <label className="text-[10px] uppercase tracking-wider text-zinc-500 font-mono">
              Position
            </label>
            <select
              value={signalId || ''}
              onChange={(e) => setSignalId(Number(e.target.value))}
              className="w-full rounded border border-[#2a2e39] bg-[#1e222d] px-2.5 py-1.5 text-xs font-mono text-zinc-300 focus:border-emerald-500 focus:outline-none"
            >
              <option value="">Select position</option>
              {positions.map((p) => (
                <option key={p.id} value={p.id}>
                  {p.symbol} {p.side} #{p.id}
                </option>
              ))}
            </select>
            {selectedPosition && (
              <p className="text-[10px] text-zinc-500">
                Entry: {selectedPosition.entry} · SL: {selectedPosition.sl ?? '—'}
              </p>
            )}
          </div>

          <div className="space-y-1.5">
            <label className="text-[10px] uppercase tracking-wider text-zinc-500 font-mono">
              Trail distance (pips)
            </label>
            <input
              type="number"
              min={MIN_PIPS}
              max={MAX_PIPS}
              value={trailPips}
              onChange={(e) => setTrailPips(Number(e.target.value) || MIN_PIPS)}
              className="w-full rounded border border-[#2a2e39] bg-[#1e222d] px-2.5 py-1.5 text-xs font-mono text-zinc-300 focus:border-emerald-500 focus:outline-none"
            />
            <p className="text-[10px] text-zinc-500">
              {MIN_PIPS} – {MAX_PIPS} pips
            </p>
          </div>

          <label className="flex items-center gap-2 cursor-pointer">
            <input
              type="checkbox"
              checked={waitForBreakeven}
              onChange={(e) => setWaitForBreakeven(e.target.checked)}
              className="rounded border-[#2a2e39] bg-[#1e222d] text-emerald-500 focus:ring-emerald-500"
            />
            <span className="text-xs text-zinc-400">Wait for breakeven before activating</span>
          </label>
        </div>

        <SheetFooter className="px-4 pb-4">
          <Button
            variant="outline"
            size="sm"
            onClick={() => onOpenChange(false)}
            className="border-[#2a2e39] text-zinc-400"
          >
            Cancel
          </Button>
          <Button
            size="sm"
            onClick={handleSubmit}
            disabled={!signalId || addTrailing.isPending}
            className="bg-emerald-600 hover:bg-emerald-500 text-white"
          >
            {addTrailing.isPending ? (
              <Loader2 className="h-4 w-4 animate-spin" />
            ) : (
              'Add trailing stop'
            )}
          </Button>
        </SheetFooter>
      </SheetContent>
    </Sheet>
  );
}
