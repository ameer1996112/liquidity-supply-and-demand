'use client';

import { useState, useMemo } from 'react';
import { useActivePositions } from '@/hooks/usePositions';
import {
  useBatchPositionAction,
  useHedgeSuggestions,
  useGenerateHedge,
  useAcceptHedge,
  useRejectHedge,
  useTrailingStops,
} from '@/hooks/useOptimizer';
import { TrailingStopDialog } from './TrailingStopDialog';
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import {
  TrendingUp,
  TrendingDown,
  MoveHorizontal,
  Shield,
  Loader2,
  AlertTriangle,
  Sparkles,
  X,
} from 'lucide-react';
import { cn } from '@/lib/utils';

export function OptimizerPanel() {
  const { data: positionsData } = useActivePositions();
  const positions = positionsData?.positions ?? [];

  const batchAction = useBatchPositionAction();
  const { data: suggestions = [], isLoading: suggestionsLoading } = useHedgeSuggestions();
  const generateHedge = useGenerateHedge();
  const acceptHedge = useAcceptHedge();
  const rejectHedge = useRejectHedge();
  const { data: trailingStops = [] } = useTrailingStops();

  const [trailingDialogOpen, setTrailingDialogOpen] = useState(false);

  const winnerIds = useMemo(
    () => positions.filter((p) => (p.live_pnl ?? 0) > 0).map((p) => p.id),
    [positions]
  );
  const loserIds = useMemo(
    () => positions.filter((p) => (p.live_pnl ?? 0) < 0).map((p) => p.id),
    [positions]
  );
  const allIds = useMemo(() => positions.map((p) => p.id), [positions]);

  const runBatch = (action: 'close' | 'move_sl_breakeven' | 'add_trailing', ids: number[]) => {
    if (ids.length === 0) return;
    batchAction.mutate({
      signal_ids: ids,
      action,
      action_params: action === 'add_trailing' ? { trail_distance_pips: 50 } : undefined,
    });
  };

  const suggestion = suggestions[0];
  const isBusy = batchAction.isPending || acceptHedge.isPending || rejectHedge.isPending;

  return (
    <div className="space-y-6">
      <TrailingStopDialog
        open={trailingDialogOpen}
        onOpenChange={setTrailingDialogOpen}
        positions={positions}
      />

      {/* Batch actions */}
      <Card className="border-[#2a2e39] bg-[#1e222d]/50">
        <CardHeader className="pb-2">
          <CardTitle className="text-sm font-medium text-zinc-100">
            Batch actions
          </CardTitle>
          <CardDescription className="text-[11px] text-zinc-500">
            Apply to current positions. Changes are sent to the backend immediately.
          </CardDescription>
        </CardHeader>
        <CardContent className="flex flex-wrap gap-2">
          <Button
            variant="outline"
            size="sm"
            onClick={() => runBatch('close', winnerIds)}
            disabled={winnerIds.length === 0 || isBusy}
            className="border-[#2a2e39] bg-[#1e222d] text-emerald-400 hover:bg-emerald-500/20 hover:border-emerald-500/50"
          >
            <TrendingUp className="h-3.5 w-3" />
            Close all winners ({winnerIds.length})
          </Button>
          <Button
            variant="outline"
            size="sm"
            onClick={() => runBatch('close', loserIds)}
            disabled={loserIds.length === 0 || isBusy}
            className="border-[#2a2e39] bg-[#1e222d] text-red-400 hover:bg-red-500/20 hover:border-red-500/50"
          >
            <TrendingDown className="h-3.5 w-3" />
            Close all losers ({loserIds.length})
          </Button>
          <Button
            variant="outline"
            size="sm"
            onClick={() => runBatch('move_sl_breakeven', allIds)}
            disabled={allIds.length === 0 || isBusy}
            className="border-[#2a2e39] bg-[#1e222d] text-zinc-300 hover:bg-[#2a2e39]"
          >
            <MoveHorizontal className="h-3.5 w-3" />
            Move all SL to breakeven
          </Button>
          <Button
            variant="outline"
            size="sm"
            onClick={() => setTrailingDialogOpen(true)}
            disabled={allIds.length === 0}
            className="border-[#2a2e39] bg-[#1e222d] text-zinc-300 hover:bg-[#2a2e39]"
          >
            Attach trailing stop…
          </Button>
          {batchAction.isPending && (
            <span className="flex items-center gap-1 text-[10px] text-amber-500">
              <Loader2 className="h-3 w-3 animate-spin" />
              Running…
            </span>
          )}
        </CardContent>
      </Card>

      {/* Hedging suggestions */}
      <Card className="border-[#2a2e39] bg-[#1e222d]/50">
        <CardHeader className="pb-2">
          <CardTitle className="text-sm font-medium text-zinc-100 flex items-center gap-2">
            <Shield className="h-4 w-4 text-amber-500" />
            Hedging
          </CardTitle>
          <CardDescription className="text-[11px] text-zinc-500">
            Reduce exposure when the hedging engine detects high risk.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-3">
          {suggestionsLoading ? (
            <p className="text-xs text-zinc-500 flex items-center gap-1">
              <Loader2 className="h-3 w-3 animate-spin" />
              Loading suggestions…
            </p>
          ) : suggestion ? (
            <div className="rounded-lg border border-amber-500/30 bg-amber-500/5 p-3 space-y-2">
              <div className="flex items-start gap-2">
                <AlertTriangle className="h-4 w-4 text-amber-500 shrink-0 mt-0.5" />
                <div className="min-w-0 flex-1">
                  <p className="text-sm font-medium text-amber-200">
                    High exposure: {suggestion.reason}
                  </p>
                  <p className="text-[11px] text-zinc-400 mt-0.5">
                    Suggested: <strong>{suggestion.suggested_direction?.toUpperCase()}</strong>{' '}
                    {suggestion.suggested_symbol} @ {suggestion.suggested_size_lots} lots
                  </p>
                </div>
              </div>
              <div className="flex flex-wrap gap-2">
                <Button
                  size="sm"
                  onClick={() => acceptHedge.mutate(suggestion.id)}
                  disabled={acceptHedge.isPending}
                  className="bg-emerald-600 hover:bg-emerald-500 text-white"
                >
                  {acceptHedge.isPending ? (
                    <Loader2 className="h-3 w-3 animate-spin" />
                  ) : (
                    'Execute hedge'
                  )}
                </Button>
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => rejectHedge.mutate(suggestion.id)}
                  disabled={rejectHedge.isPending}
                  className="border-[#2a2e39] text-zinc-400"
                >
                  <X className="h-3 w-3" />
                  Dismiss
                </Button>
              </div>
            </div>
          ) : (
            <div className="flex flex-wrap items-center gap-2">
              <p className="text-xs text-zinc-500">No pending hedge suggestions.</p>
              <Button
                variant="outline"
                size="sm"
                onClick={() => generateHedge.mutate()}
                disabled={generateHedge.isPending || positions.length === 0}
                className="border-[#2a2e39] text-zinc-400"
              >
                {generateHedge.isPending ? (
                  <Loader2 className="h-3 w-3 animate-spin" />
                ) : (
                  <Sparkles className="h-3 w-3" />
                )}
                Analyze portfolio
              </Button>
            </div>
          )}
        </CardContent>
      </Card>

      {/* Active trailing stops */}
      {trailingStops.length > 0 && (
        <Card className="border-[#2a2e39] bg-[#1e222d]/50">
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium text-zinc-100">
              Active trailing stops
            </CardTitle>
            <CardDescription className="text-[11px] text-zinc-500">
              {trailingStops.length} position(s) with trailing stop attached.
            </CardDescription>
          </CardHeader>
          <CardContent>
            <ul className="space-y-1.5">
              {trailingStops.map((ts: any) => (
                <li
                  key={ts.id}
                  className={cn(
                    'flex items-center justify-between rounded border border-[#2a2e39] px-2.5 py-1.5',
                    'text-xs font-mono text-zinc-300'
                  )}
                >
                  <span>
                    {ts.symbol} #{ts.signal_id} · {ts.trail_distance_pips} pips
                    {ts.is_activated && (
                      <Badge className="ml-1.5 bg-emerald-500/20 text-emerald-400 text-[10px]">
                        Active
                      </Badge>
                    )}
                  </span>
                </li>
              ))}
            </ul>
          </CardContent>
        </Card>
      )}
    </div>
  );
}
