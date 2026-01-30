'use client';

import { TradingSignal } from '@/types/trading';
import {
  Sheet,
  SheetContent,
  SheetHeader,
  SheetTitle,
} from '@/components/ui/sheet';
import { Badge } from '@/components/ui/badge';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Separator } from '@/components/ui/separator';
import { ScrollArea } from '@/components/ui/scroll-area';
import {
  Check,
  X,
  TrendingUp,
  TrendingDown,
  Target,
  Shield,
  Zap,
  Brain,
  Activity,
  BarChart3,
  Droplets,
  Gauge,
} from 'lucide-react';
import { cn } from '@/lib/utils';
import { format } from 'date-fns';

interface SignalInspectorProps {
  signal: TradingSignal | null;
  open: boolean;
  onOpenChange: (open: boolean) => void;
}

// Info row component
function InfoRow({
  label,
  value,
  valueClass,
}: {
  label: string;
  value: React.ReactNode;
  valueClass?: string;
}) {
  return (
    <div className="flex items-center justify-between py-1.5">
      <span className="text-xs text-zinc-500">{label}</span>
      <span className={cn('font-mono text-sm text-zinc-100', valueClass)}>
        {value}
      </span>
    </div>
  );
}

// Boolean indicator component
function BoolIndicator({ value, label }: { value: boolean; label: string }) {
  return (
    <div className="flex items-center gap-2">
      <div
        className={cn(
          'w-5 h-5 rounded flex items-center justify-center',
          value ? 'bg-emerald-500/20 text-emerald-400' : 'bg-zinc-800 text-zinc-500'
        )}
      >
        {value ? <Check className="w-3 h-3" /> : <X className="w-3 h-3" />}
      </div>
      <span className="text-xs text-zinc-400">{label}</span>
    </div>
  );
}

// Score display component
function ScoreDisplay({
  label,
  value,
  icon,
  max = 100,
}: {
  label: string;
  value: number;
  icon: React.ReactNode;
  max?: number;
}) {
  const percentage = (value / max) * 100;
  const getColor = (p: number) => {
    if (p >= 70) return 'bg-emerald-500';
    if (p >= 50) return 'bg-amber-500';
    return 'bg-red-500';
  };

  return (
    <div className="flex flex-col gap-1.5">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-1.5">
          <div className="text-zinc-500">{icon}</div>
          <span className="text-xs text-zinc-400">{label}</span>
        </div>
        <span className="font-mono text-xs text-zinc-300">{value.toFixed(1)}</span>
      </div>
      <div className="w-full h-1 bg-zinc-800 rounded-full overflow-hidden">
        <div
          className={cn('h-full rounded-full transition-all', getColor(percentage))}
          style={{ width: `${Math.min(percentage, 100)}%` }}
        />
      </div>
    </div>
  );
}

export function SignalInspector({
  signal,
  open,
  onOpenChange,
}: SignalInspectorProps) {
  if (!signal) return null;

  const { ai_reasoning: ai } = signal;
  const isBuy = signal.action === 'BUY';

  return (
    <Sheet open={open} onOpenChange={onOpenChange}>
      <SheetContent className="w-full sm:max-w-lg bg-zinc-950 border-zinc-800 p-0">
        <ScrollArea className="h-full">
          <div className="p-6">
            {/* Header */}
            <SheetHeader className="mb-6">
              <div className="flex items-center gap-3 mb-2">
                <Badge
                  variant="outline"
                  className={cn(
                    'text-xs font-bold px-2 py-0.5 border-0',
                    isBuy
                      ? 'bg-emerald-500/20 text-emerald-400'
                      : 'bg-red-500/20 text-red-400'
                  )}
                >
                  {signal.action}
                </Badge>
                <Badge
                  variant="outline"
                  className={cn(
                    'text-xs px-2 py-0.5 border border-zinc-700',
                    signal.status === 'EXECUTED'
                      ? 'text-emerald-400'
                      : signal.status === 'FILTERED'
                      ? 'text-amber-400'
                      : 'text-red-400'
                  )}
                >
                  {signal.status}
                </Badge>
                {ai.is_accuracy && (
                  <Badge
                    variant="outline"
                    className="text-xs px-2 py-0.5 border-0 bg-purple-500/20 text-purple-400"
                  >
                    ⭐ ACCURACY
                  </Badge>
                )}
              </div>
              <SheetTitle className="flex items-baseline gap-2 text-left">
                <span className="font-mono text-2xl font-bold text-zinc-100">
                  {signal.ticker}
                </span>
                <span className="font-mono text-lg text-zinc-400">
                  @{signal.price.toFixed(signal.ticker.includes('JPY') ? 3 : 5)}
                </span>
              </SheetTitle>
              <p className="text-xs text-zinc-500 font-mono">
                {format(new Date(signal.created_at), 'PPpp')}
              </p>
            </SheetHeader>

            {/* Filter Reason (if filtered) */}
            {signal.status === 'FILTERED' && signal.filter_reason && (
              <div className="mb-4 p-3 rounded-lg bg-amber-500/10 border border-amber-500/20">
                <div className="flex items-center gap-2 mb-1">
                  <Shield className="w-4 h-4 text-amber-400" />
                  <span className="text-xs font-semibold text-amber-400 uppercase">
                    Filter Reason
                  </span>
                </div>
                <p className="text-sm text-amber-200/80 font-mono">
                  {signal.filter_reason}
                </p>
              </div>
            )}

            {/* Technical Card */}
            <Card className="bg-zinc-900/50 border-zinc-800 mb-4">
              <CardHeader className="py-3 px-4">
                <CardTitle className="text-xs font-semibold text-zinc-400 uppercase tracking-wider flex items-center gap-2">
                  <Target className="w-4 h-4" />
                  Technical Setup
                </CardTitle>
              </CardHeader>
              <CardContent className="py-2 px-4">
                <InfoRow label="Entry Price" value={signal.price.toFixed(5)} />
                <InfoRow
                  label="Stop Loss"
                  value={signal.stop_loss.toFixed(5)}
                  valueClass="text-red-400"
                />
                <InfoRow
                  label="Take Profit"
                  value={signal.take_profit.toFixed(5)}
                  valueClass="text-emerald-400"
                />
                <Separator className="my-2 bg-zinc-800" />
                <InfoRow label="Position Size" value={`${signal.position_size} lots`} />
                <InfoRow label="Risk:Reward" value={`1:${signal.rr_ratio?.toFixed(2) || '—'}`} />
                <InfoRow label="SL Distance" value={`${signal.sl_pips?.toFixed(1) || '—'} pips`} />
                {signal.pnl !== undefined && (
                  <>
                    <Separator className="my-2 bg-zinc-800" />
                    <InfoRow
                      label="Realized PnL"
                      value={`${signal.pnl >= 0 ? '+' : ''}$${signal.pnl.toFixed(2)}`}
                      valueClass={signal.pnl >= 0 ? 'text-emerald-400' : 'text-red-400'}
                    />
                    {signal.exit_type && (
                      <InfoRow
                        label="Exit Type"
                        value={signal.exit_type.replace('_', ' ')}
                      />
                    )}
                  </>
                )}
              </CardContent>
            </Card>

            {/* Zone Information */}
            <Card className="bg-zinc-900/50 border-zinc-800 mb-4">
              <CardHeader className="py-3 px-4">
                <CardTitle className="text-xs font-semibold text-zinc-400 uppercase tracking-wider flex items-center gap-2">
                  <BarChart3 className="w-4 h-4" />
                  Zone Analysis
                </CardTitle>
              </CardHeader>
              <CardContent className="py-2 px-4">
                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <InfoRow label="Zone ID" value={`#${ai.zone_id}`} />
                    <InfoRow
                      label="Zone Type"
                      value={
                        <Badge
                          variant="outline"
                          className={cn(
                            'text-[10px] border-0 px-1.5 py-0',
                            ai.zone_type === 'demand'
                              ? 'bg-emerald-500/20 text-emerald-400'
                              : 'bg-red-500/20 text-red-400'
                          )}
                        >
                          {ai.zone_type.toUpperCase()}
                        </Badge>
                      }
                    />
                    <InfoRow
                      label="Grade"
                      value={
                        <span className="font-bold">{ai.zone_grade}</span>
                      }
                    />
                  </div>
                  <div>
                    <InfoRow label="Entry Model" value={ai.entry_model} />
                    <InfoRow
                      label="Session"
                      value={
                        ai.session === 0
                          ? 'Asian'
                          : ai.session === 1
                          ? 'London'
                          : ai.session === 2
                          ? 'NY'
                          : 'Off-hours'
                      }
                    />
                    <InfoRow
                      label="Trend"
                      value={
                        <div className="flex items-center gap-1">
                          {ai.trend === 1 ? (
                            <>
                              <TrendingUp className="w-3 h-3 text-emerald-400" />
                              <span className="text-emerald-400">Up</span>
                            </>
                          ) : (
                            <>
                              <TrendingDown className="w-3 h-3 text-red-400" />
                              <span className="text-red-400">Down</span>
                            </>
                          )}
                        </div>
                      }
                    />
                  </div>
                </div>
              </CardContent>
            </Card>

            {/* Liquidity Checks */}
            <Card className="bg-zinc-900/50 border-zinc-800 mb-4">
              <CardHeader className="py-3 px-4">
                <CardTitle className="text-xs font-semibold text-zinc-400 uppercase tracking-wider flex items-center gap-2">
                  <Droplets className="w-4 h-4" />
                  Liquidity Analysis
                </CardTitle>
              </CardHeader>
              <CardContent className="py-3 px-4">
                <div className="grid grid-cols-2 gap-x-6 gap-y-2">
                  <BoolIndicator value={ai.liquidity_swept} label="Liquidity Swept" />
                  <BoolIndicator value={ai.target_swept} label="Target Swept" />
                  <BoolIndicator value={ai.caused_sweep} label="Caused Sweep" />
                  <BoolIndicator
                    value={ai.guardian_structure_break || false}
                    label="Structure Break"
                  />
                </div>
                <Separator className="my-3 bg-zinc-800" />
                <div className="grid grid-cols-2 gap-2">
                  <InfoRow
                    label="Liq Distance"
                    value={`${ai.liquidity_distance.toFixed(1)} pips`}
                  />
                  <InfoRow
                    label="Liq Spread"
                    value={`${ai.liquidity_spread.toFixed(1)} pips`}
                  />
                </div>
                {ai.guardian_arrival && (
                  <div className="mt-2">
                    <InfoRow
                      label="Arrival Type"
                      value={
                        <Badge
                          variant="outline"
                          className={cn(
                            'text-[10px] border-0 px-1.5 py-0',
                            ai.guardian_arrival === 'aggressive'
                              ? 'bg-emerald-500/20 text-emerald-400'
                              : 'bg-amber-500/20 text-amber-400'
                          )}
                        >
                          {ai.guardian_arrival.toUpperCase()}
                        </Badge>
                      }
                    />
                  </div>
                )}
              </CardContent>
            </Card>

            {/* AI Brain Metrics */}
            <Card className="bg-zinc-900/50 border-zinc-800 mb-4">
              <CardHeader className="py-3 px-4">
                <CardTitle className="text-xs font-semibold text-zinc-400 uppercase tracking-wider flex items-center gap-2">
                  <Brain className="w-4 h-4" />
                  AI Metrics
                </CardTitle>
              </CardHeader>
              <CardContent className="py-3 px-4 space-y-3">
                <ScoreDisplay
                  label="Zone Score"
                  value={ai.zone_score}
                  icon={<Gauge className="w-3 h-3" />}
                />
                <ScoreDisplay
                  label="Base Quality"
                  value={ai.base_quality}
                  icon={<Activity className="w-3 h-3" />}
                />
                <ScoreDisplay
                  label="Departure Strength"
                  value={ai.departure_strength}
                  icon={<Zap className="w-3 h-3" />}
                />
                <ScoreDisplay
                  label="Return Strength"
                  value={ai.return_strength}
                  icon={<TrendingUp className="w-3 h-3" />}
                />
                <Separator className="my-2 bg-zinc-800" />
                <div className="grid grid-cols-3 gap-2">
                  <div className="text-center p-2 bg-zinc-800/50 rounded">
                    <div className="font-mono text-sm font-bold text-zinc-100">
                      {ai.rsi.toFixed(1)}
                    </div>
                    <div className="text-[10px] text-zinc-500">RSI</div>
                  </div>
                  <div className="text-center p-2 bg-zinc-800/50 rounded">
                    <div className="font-mono text-sm font-bold text-zinc-100">
                      {ai.adx.toFixed(1)}
                    </div>
                    <div className="text-[10px] text-zinc-500">ADX</div>
                  </div>
                  <div className="text-center p-2 bg-zinc-800/50 rounded">
                    <div className="font-mono text-sm font-bold text-zinc-100">
                      {ai.rvol.toFixed(2)}x
                    </div>
                    <div className="text-[10px] text-zinc-500">RVOL</div>
                  </div>
                </div>
              </CardContent>
            </Card>

            {/* AI Confidence */}
            <Card className="bg-gradient-to-br from-zinc-900/50 to-zinc-900/30 border-zinc-800">
              <CardContent className="py-4 px-4">
                <div className="flex items-center justify-between mb-2">
                  <span className="text-xs text-zinc-400 uppercase tracking-wider">
                    AI Confidence
                  </span>
                  <span
                    className={cn(
                      'font-mono text-2xl font-bold',
                      signal.ai_confidence >= 70
                        ? 'text-emerald-400'
                        : signal.ai_confidence >= 50
                        ? 'text-amber-400'
                        : 'text-red-400'
                    )}
                  >
                    {signal.ai_confidence}%
                  </span>
                </div>
                <div className="w-full h-2 bg-zinc-800 rounded-full overflow-hidden">
                  <div
                    className={cn(
                      'h-full rounded-full transition-all',
                      signal.ai_confidence >= 70
                        ? 'bg-emerald-500'
                        : signal.ai_confidence >= 50
                        ? 'bg-amber-500'
                        : 'bg-red-500'
                    )}
                    style={{ width: `${signal.ai_confidence}%` }}
                  />
                </div>
              </CardContent>
            </Card>
          </div>
        </ScrollArea>
      </SheetContent>
    </Sheet>
  );
}
