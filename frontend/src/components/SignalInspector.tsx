'use client';

import { TradingSignal, AIReasoning, getSymbol, getSide, getScore, getPnl, getNotes } from '@/types/trading';
import {
  Sheet,
  SheetContent,
  SheetDescription,
  SheetHeader,
  SheetTitle,
} from '@/components/ui/sheet';
import { Badge } from '@/components/ui/badge';
import { Separator } from '@/components/ui/separator';
import { ScrollArea } from '@/components/ui/scroll-area';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { cn } from '@/lib/utils';
import { format } from 'date-fns';
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
  Code2,
  FileText,
  Copy,
  CheckCircle2,
} from 'lucide-react';
import { useState } from 'react';

interface SignalInspectorProps {
  signal: TradingSignal | null;
  open: boolean;
  onOpenChange: (open: boolean) => void;
}

// Safe number formatter
const formatNum = (num: number | null | undefined, decimals = 2): string =>
  num != null ? num.toFixed(decimals) : '--';

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
      <span className="text-[11px] text-zinc-500 uppercase tracking-wider">{label}</span>
      <span className={cn('font-mono text-sm text-zinc-100', valueClass)}>
        {value}
      </span>
    </div>
  );
}

// Boolean indicator component
function BoolIndicator({ value, label }: { value: boolean | undefined; label: string }) {
  const isTrue = value === true;
  return (
    <div className="flex items-center gap-2">
      <div
        className={cn(
          'w-5 h-5 rounded flex items-center justify-center',
          isTrue ? 'bg-emerald-500/20 text-emerald-400' : 'bg-zinc-800 text-zinc-600'
        )}
      >
        {isTrue ? <Check className="w-3 h-3" /> : <X className="w-3 h-3" />}
      </div>
      <span className="text-[11px] text-zinc-400">{label}</span>
    </div>
  );
}

// Score display component with progress bar
function ScoreBar({
  label,
  value,
  icon,
  max = 100,
}: {
  label: string;
  value: number | undefined;
  icon: React.ReactNode;
  max?: number;
}) {
  if (value == null) return null;

  const percentage = Math.min((value / max) * 100, 100);
  const getColor = (p: number) => {
    if (p >= 70) return 'bg-emerald-500';
    if (p >= 50) return 'bg-amber-500';
    return 'bg-rose-500';
  };

  return (
    <div className="flex flex-col gap-1.5">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-1.5">
          <div className="text-zinc-500">{icon}</div>
          <span className="text-[11px] text-zinc-400">{label}</span>
        </div>
        <span className="font-mono text-xs text-zinc-300">{value.toFixed(1)}</span>
      </div>
      <div className="w-full h-1 bg-zinc-800 rounded-full overflow-hidden">
        <div
          className={cn('h-full rounded-full transition-all', getColor(percentage))}
          style={{ width: `${percentage}%` }}
        />
      </div>
    </div>
  );
}

// JSON viewer component with copy functionality
function JsonViewer({ data, title }: { data: unknown; title: string }) {
  const [copied, setCopied] = useState(false);

  const jsonString = JSON.stringify(data, null, 2);

  const handleCopy = async () => {
    await navigator.clipboard.writeText(jsonString);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  return (
    <div className="rounded-lg border border-zinc-800 bg-zinc-950 overflow-hidden">
      <div className="flex items-center justify-between px-3 py-2 border-b border-zinc-800 bg-zinc-900/50">
        <span className="text-[11px] text-zinc-400 font-mono uppercase tracking-wider">{title}</span>
        <button
          onClick={handleCopy}
          className="flex items-center gap-1 text-[10px] text-zinc-500 hover:text-zinc-300 transition-colors"
        >
          {copied ? (
            <>
              <CheckCircle2 className="w-3 h-3 text-emerald-400" />
              <span className="text-emerald-400">Copied!</span>
            </>
          ) : (
            <>
              <Copy className="w-3 h-3" />
              <span>Copy</span>
            </>
          )}
        </button>
      </div>
      <ScrollArea className="h-64">
        <pre className="p-3 text-[11px] text-zinc-400 font-mono leading-relaxed whitespace-pre-wrap break-words">
          {jsonString}
        </pre>
      </ScrollArea>
    </div>
  );
}

// Parse AI reasoning - handle both string and object, then merge
// signal-level zone fields as fallbacks (save_alert stores them as
// top-level DB columns, not inside ai_reasoning).
function parseAIReasoning(signal: TradingSignal): AIReasoning | null {
  let ai: AIReasoning | null = null;

  if (signal.ai_reasoning) {
    if (typeof signal.ai_reasoning === 'string') {
      try {
        ai = JSON.parse(signal.ai_reasoning);
      } catch {
        ai = null;
      }
    } else {
      ai = signal.ai_reasoning as AIReasoning;
    }
  }

  // Merge signal-level zone/metric fields as fallbacks so Zone Analysis
  // displays data even when ai_reasoning doesn't contain these fields.
  const fallbacks: Partial<AIReasoning> = {
    zone_id: signal.zone_id,
    zone_type: signal.zone_type as AIReasoning['zone_type'],
    zone_grade: signal.zone_grade,
    zone_score: signal.score ?? signal.ai_confidence,
    entry_model: signal.entry_model,
    liquidity_swept: signal.liq_swept,
    target_swept: signal.target_swept,
    caused_sweep: signal.caused_sweep,
    is_accuracy: signal.is_accuracy,
    session: signal.session,
    trend: signal.trend,
    htf_trend: signal.htf_trend,
    rsi: signal.rsi,
    rvol: signal.rvol,
    adx: signal.adx,
    atr_ratio: signal.atr_ratio,
    base_quality: signal.base_quality,
    departure_strength: signal.departure_strength,
    liquidity_distance: signal.liquidity_distance,
    liquidity_spread: signal.liquidity_spread,
    liquidity_distance_pips: signal.liquidity_distance_pips,
    liquidity_spread_pips: signal.liquidity_spread_pips,
    return_strength: signal.return_strength,
  };

  if (!ai) {
    // No ai_reasoning at all — build from signal-level fields only
    const hasAny = Object.values(fallbacks).some((v) => v != null);
    return hasAny ? (fallbacks as AIReasoning) : null;
  }

  // Merge: ai_reasoning values take precedence, signal-level fill gaps
  for (const [key, val] of Object.entries(fallbacks)) {
    if (val != null && (ai as Record<string, unknown>)[key] == null) {
      (ai as Record<string, unknown>)[key] = val;
    }
  }

  return ai;
}

export function SignalInspector({
  signal,
  open,
  onOpenChange,
}: SignalInspectorProps) {
  if (!signal) return null;

  const symbol = getSymbol(signal);
  const side = getSide(signal);
  const score = getScore(signal);
  const pnl = getPnl(signal);
  const notes = getNotes(signal);
  const ai = parseAIReasoning(signal);
  const isBuy = side === 'buy';
  const hasLegacyMetrics =
    !!ai &&
    (ai.zone_score != null ||
      ai.base_quality != null ||
      ai.departure_strength != null ||
      ai.return_strength != null ||
      ai.rsi != null ||
      ai.adx != null ||
      ai.rvol != null ||
      signal.base_quality != null ||
      signal.departure_strength != null ||
      signal.return_strength != null ||
      signal.rsi != null ||
      signal.adx != null ||
      signal.rvol != null);
  const entryPrice = signal.price ?? signal.entry;
  const stopLoss = signal.stop_loss ?? signal.sl;
  const takeProfit = signal.take_profit ?? signal.tp;

  return (
    <Sheet open={open} onOpenChange={onOpenChange}>
      <SheetContent className="w-full sm:max-w-xl bg-zinc-950 border-zinc-800 p-0" aria-describedby="signal-inspector-desc">
        <SheetDescription id="signal-inspector-desc" className="sr-only">Trade details and AI reasoning</SheetDescription>
        <ScrollArea className="h-full">
          <div className="p-6">
            {/* Header */}
            <SheetHeader className="mb-6">
              <div className="flex items-center gap-2 mb-2">
                <Badge
                  className={cn(
                    'text-xs font-bold px-2.5 py-1 border-0',
                    isBuy
                      ? 'bg-emerald-500/20 text-emerald-400'
                      : 'bg-rose-500/20 text-rose-400'
                  )}
                >
                  {side.toUpperCase()}
                </Badge>
                <Badge
                  className={cn(
                    'text-xs px-2 py-0.5 border border-zinc-700',
                    signal.status?.toLowerCase() === 'active'
                      ? 'text-blue-400 border-blue-500/30'
                      : signal.status?.toLowerCase() === 'ai_rejected'
                      ? 'text-rose-400 border-rose-500/30'
                      : 'text-zinc-400'
                  )}
                >
                  {signal.status?.toUpperCase()}
                </Badge>
                {ai?.is_accuracy && (
                  <Badge className="text-xs px-2 py-0.5 border-0 bg-purple-500/20 text-purple-400">
                    ACCURACY
                  </Badge>
                )}
              </div>
              <SheetTitle className="flex items-baseline gap-2 text-left">
                <span className="font-mono text-2xl font-bold text-zinc-100">
                  {symbol}
                </span>
                {entryPrice && (
                  <span className="font-mono text-lg text-zinc-400">
                    @{formatNum(entryPrice, symbol.includes('JPY') ? 3 : symbol.includes('BTC') ? 2 : 5)}
                  </span>
                )}
              </SheetTitle>
              <p className="text-xs text-zinc-500 font-mono">
                {format(new Date(signal.created_at), 'PPpp')}
              </p>
            </SheetHeader>

            {/* Tabs */}
            <Tabs defaultValue="overview" className="w-full">
              <TabsList className="w-full bg-zinc-900/50 border border-zinc-800 p-1 mb-4">
                <TabsTrigger
                  value="overview"
                  className="flex-1 data-[state=active]:bg-zinc-800 text-xs font-mono uppercase"
                >
                  <Activity className="w-3 h-3 mr-1.5" />
                  Overview
                </TabsTrigger>
                <TabsTrigger
                  value="ai"
                  className="flex-1 data-[state=active]:bg-zinc-800 text-xs font-mono uppercase"
                >
                  <Brain className="w-3 h-3 mr-1.5" />
                  AI Brain
                </TabsTrigger>
                <TabsTrigger
                  value="raw"
                  className="flex-1 data-[state=active]:bg-zinc-800 text-xs font-mono uppercase"
                >
                  <Code2 className="w-3 h-3 mr-1.5" />
                  Raw Data
                </TabsTrigger>
              </TabsList>

              {/* Overview Tab */}
              <TabsContent value="overview" className="space-y-4 mt-0">
                {/* AI Reasoning / Notes */}
                {notes && (
                  <div className="p-3 rounded-lg bg-zinc-900/50 border border-zinc-800">
                    <div className="flex items-center gap-2 mb-2">
                      <FileText className="w-4 h-4 text-zinc-500" />
                      <span className="text-[11px] text-zinc-500 uppercase tracking-wider">
                        AI Reasoning
                      </span>
                    </div>
                    <p className="text-sm text-zinc-300 leading-relaxed">{notes}</p>
                  </div>
                )}

                {/* Filter/Rejection Reason */}
                {signal.filter_reason && signal.status?.toLowerCase() !== 'active' && (
                  <div className="p-3 rounded-lg bg-amber-500/10 border border-amber-500/20">
                    <div className="flex items-center gap-2 mb-1">
                      <Shield className="w-4 h-4 text-amber-400" />
                      <span className="text-[11px] font-semibold text-amber-400 uppercase">
                        Filter Reason
                      </span>
                    </div>
                    <p className="text-sm text-amber-200/80">{signal.filter_reason}</p>
                  </div>
                )}

                {/* Technical Setup */}
                <div className="rounded-lg bg-zinc-900/50 border border-zinc-800 overflow-hidden">
                  <div className="px-4 py-2.5 border-b border-zinc-800 flex items-center gap-2">
                    <Target className="w-4 h-4 text-zinc-500" />
                    <span className="text-[11px] text-zinc-400 uppercase tracking-wider">
                      Technical Setup
                    </span>
                  </div>
                  <div className="p-4 space-y-1">
                    {entryPrice && <InfoRow label="Entry" value={`$${formatNum(entryPrice, 5)}`} />}
                    {stopLoss && (
                      <InfoRow
                        label="Stop Loss"
                        value={`$${formatNum(stopLoss, 5)}`}
                        valueClass="text-rose-400"
                      />
                    )}
                    {takeProfit && (
                      <InfoRow
                        label="Take Profit"
                        value={`$${formatNum(takeProfit, 5)}`}
                        valueClass="text-emerald-400"
                      />
                    )}
                    <Separator className="my-2 bg-zinc-800" />
                    {signal.position_size && (
                      <InfoRow label="Position Size" value={`${signal.position_size} lots`} />
                    )}
                    {signal.rr_ratio && (
                      <InfoRow label="Risk:Reward" value={`1:${formatNum(signal.rr_ratio, 2)}`} />
                    )}
                    {signal.sl_pips && (
                      <InfoRow label="SL Distance" value={`${formatNum(signal.sl_pips, 1)} pips`} />
                    )}

                    {/* PnL Section */}
                    {pnl !== null && (
                      <>
                        <Separator className="my-2 bg-zinc-800" />
                        <InfoRow
                          label="Realized PnL"
                          value={`${pnl >= 0 ? '+' : ''}$${formatNum(pnl, 2)}`}
                          valueClass={pnl >= 0 ? 'text-emerald-400' : 'text-rose-400'}
                        />
                        {signal.pnl_percentage != null && (
                          <InfoRow
                            label="PnL %"
                            value={`${signal.pnl_percentage >= 0 ? '+' : ''}${formatNum(signal.pnl_percentage, 2)}%`}
                            valueClass={signal.pnl_percentage >= 0 ? 'text-emerald-400' : 'text-rose-400'}
                          />
                        )}
                        {signal.exit_type && (
                          <InfoRow label="Exit Type" value={signal.exit_type.replace('_', ' ')} />
                        )}
                      </>
                    )}
                  </div>
                </div>

                {/* AI Confidence */}
                {score !== null && (
                  <div className="rounded-lg bg-gradient-to-br from-zinc-900/50 to-zinc-900/30 border border-zinc-800 p-4">
                    <div className="flex items-center justify-between mb-2">
                      <span className="text-[11px] text-zinc-400 uppercase tracking-wider">
                        AI Confidence
                      </span>
                      <span
                        className={cn(
                          'font-mono text-2xl font-bold',
                          score >= 70
                            ? 'text-emerald-400'
                            : score >= 50
                            ? 'text-amber-400'
                            : 'text-rose-400'
                        )}
                      >
                        {score}%
                      </span>
                    </div>
                    <div className="w-full h-2 bg-zinc-800 rounded-full overflow-hidden">
                      <div
                        className={cn(
                          'h-full rounded-full transition-all',
                          score >= 70
                            ? 'bg-emerald-500'
                            : score >= 50
                            ? 'bg-amber-500'
                            : 'bg-rose-500'
                        )}
                        style={{ width: `${score}%` }}
                      />
                    </div>
                  </div>
                )}
              </TabsContent>

              {/* AI Brain Tab */}
              <TabsContent value="ai" className="space-y-4 mt-0">
                {ai ? (
                  <>
                    {/* Ensemble Decision Summary */}
                    <div className="rounded-lg bg-zinc-900/50 border border-zinc-800 overflow-hidden">
                      <div className="px-4 py-2.5 border-b border-zinc-800 flex items-center gap-2">
                        <Shield className="w-4 h-4 text-zinc-500" />
                        <span className="text-[11px] text-zinc-400 uppercase tracking-wider">
                          Ensemble Decision
                        </span>
                      </div>
                      <div className="p-4 space-y-3">
                        <div className="flex items-center justify-between">
                          <span className="text-[11px] text-zinc-500 uppercase tracking-wider">
                            Decision
                          </span>
                          <span
                            className={cn(
                              'font-mono text-sm font-bold px-2 py-0.5 rounded',
                              ai.decision === 'GO' && 'bg-emerald-500/20 text-emerald-400',
                              ai.decision === 'NO_GO' && 'bg-rose-500/20 text-rose-400',
                              !ai.decision || (ai.decision !== 'GO' && ai.decision !== 'NO_GO')
                                ? 'bg-zinc-600/30 text-zinc-400'
                                : '',
                            )}
                          >
                            {(ai.decision ?? signal.status ?? 'unknown').toString().toUpperCase()}
                          </span>
                        </div>

                        {/* RF / AI confidence bar (reuses main score) */}
                        {score !== null && (
                          <ScoreBar
                            label="AI Confidence"
                            value={score}
                            icon={<Gauge className="w-3 h-3" />}
                          />
                        )}

                        {ai.reason && (
                          <div className="text-sm text-zinc-300 leading-relaxed">
                            {ai.reason}
                          </div>
                        )}

                        {ai.narrative && (
                          <div className="text-xs text-zinc-400 leading-relaxed">
                            <span className="block text-[11px] text-zinc-500 uppercase tracking-wider mb-1">
                              Market Narrative
                            </span>
                            <p>{ai.narrative}</p>
                          </div>
                        )}

                        {Array.isArray(ai.rules) && ai.rules.length > 0 && (
                          <div className="text-xs text-zinc-300">
                            <span className="block text-[11px] text-zinc-500 uppercase tracking-wider mb-1">
                              RAG Rules (Top {Math.min(ai.rules.length, 5)})
                            </span>
                            <ul className="list-disc pl-4 space-y-1">
                              {ai.rules.slice(0, 5).map((rule, idx) => (
                                // eslint-disable-next-line react/no-array-index-key
                                <li key={idx}>{String(rule)}</li>
                              ))}
                            </ul>
                          </div>
                        )}
                      </div>
                    </div>

                    {/* Zone Analysis */}
                    <div className="rounded-lg bg-zinc-900/50 border border-zinc-800 overflow-hidden">
                      <div className="px-4 py-2.5 border-b border-zinc-800 flex items-center gap-2">
                        <BarChart3 className="w-4 h-4 text-zinc-500" />
                        <span className="text-[11px] text-zinc-400 uppercase tracking-wider">
                          Zone Analysis
                        </span>
                      </div>
                      <div className="p-4 grid grid-cols-2 gap-4">
                        <div>
                          {ai.zone_id && <InfoRow label="Zone ID" value={`#${ai.zone_id}`} />}
                          {ai.zone_type && (
                            <InfoRow
                              label="Type"
                              value={
                                <Badge
                                  className={cn(
                                    'text-[10px] border-0 px-1.5 py-0',
                                    ai.zone_type === 'demand'
                                      ? 'bg-emerald-500/20 text-emerald-400'
                                      : 'bg-rose-500/20 text-rose-400'
                                  )}
                                >
                                  {ai.zone_type.toUpperCase()}
                                </Badge>
                              }
                            />
                          )}
                          {ai.zone_grade && <InfoRow label="Grade" value={ai.zone_grade} />}
                        </div>
                        <div>
                          {ai.entry_model && <InfoRow label="Entry Model" value={ai.entry_model} />}
                          {ai.session != null && (
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
                          )}
                          {ai.trend != null && (
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
                                      <TrendingDown className="w-3 h-3 text-rose-400" />
                                      <span className="text-rose-400">Down</span>
                                    </>
                                  )}
                                </div>
                              }
                            />
                          )}
                        </div>
                      </div>
                    </div>

                    {/* Liquidity Analysis */}
                    <div className="rounded-lg bg-zinc-900/50 border border-zinc-800 overflow-hidden">
                      <div className="px-4 py-2.5 border-b border-zinc-800 flex items-center gap-2">
                        <Droplets className="w-4 h-4 text-zinc-500" />
                        <span className="text-[11px] text-zinc-400 uppercase tracking-wider">
                          Liquidity Analysis
                        </span>
                      </div>
                      <div className="p-4 space-y-3">
                        <div className="grid grid-cols-2 gap-x-6 gap-y-2">
                          <BoolIndicator value={ai.liquidity_swept} label="Liquidity Swept" />
                          <BoolIndicator value={ai.target_swept} label="Target Swept" />
                          <BoolIndicator value={ai.caused_sweep} label="Caused Sweep" />
                          <BoolIndicator value={ai.guardian_structure_break} label="Structure Break" />
                        </div>
                        <Separator className="bg-zinc-800" />
                        <div className="grid grid-cols-2 gap-2">
                          {(ai.liquidity_distance_pips != null || ai.liquidity_distance != null) && (
                            <InfoRow
                              label="Distance"
                              value={
                                ai.liquidity_distance_pips != null
                                  ? `${formatNum(ai.liquidity_distance_pips, 1)} pips`
                                  : ai.liquidity_distance != null && ai.liquidity_distance > 0
                                    ? `~${formatNum((1 - ai.liquidity_distance / 100) * 50, 1)} pips`
                                    : ai.liquidity_distance === 0
                                      ? '>50 pips'
                                      : 'N/A'
                              }
                            />
                          )}
                          {(ai.liquidity_spread_pips != null || ai.liquidity_spread != null) && (
                            <InfoRow
                              label="Spread"
                              value={
                                ai.liquidity_spread_pips != null
                                  ? `${formatNum(ai.liquidity_spread_pips, 1)} pips`
                                  : `${formatNum(ai.liquidity_spread!, 1)} pips`
                              }
                            />
                          )}
                        </div>
                      </div>
                    </div>

                    {/* AI Metrics */}
                    <div className="rounded-lg bg-zinc-900/50 border border-zinc-800 overflow-hidden">
                      <div className="px-4 py-2.5 border-b border-zinc-800 flex items-center gap-2">
                        <Brain className="w-4 h-4 text-zinc-500" />
                        <span className="text-[11px] text-zinc-400 uppercase tracking-wider">
                          AI Metrics
                        </span>
                      </div>
                      <div className="p-4 space-y-3">
                        {hasLegacyMetrics ? (
                          <>
                            <ScoreBar
                              label="Zone Score"
                              value={ai.zone_score}
                              icon={<Gauge className="w-3 h-3" />}
                            />
                            <ScoreBar
                              label="Base Quality"
                              value={ai.base_quality}
                              icon={<Activity className="w-3 h-3" />}
                            />
                            <ScoreBar
                              label="Departure Strength"
                              value={ai.departure_strength}
                              icon={<Zap className="w-3 h-3" />}
                            />
                            <ScoreBar
                              label="Return Strength"
                              value={ai.return_strength}
                              icon={<TrendingUp className="w-3 h-3" />}
                            />

                            {/* Indicator Stats */}
                            <Separator className="bg-zinc-800" />
                            <div className="grid grid-cols-3 gap-2">
                              {ai.rsi != null && (
                                <div className="text-center p-2 bg-zinc-800/50 rounded">
                                  <div className="font-mono text-sm font-bold text-zinc-100">
                                    {formatNum(ai.rsi, 1)}
                                  </div>
                                  <div className="text-[10px] text-zinc-500">RSI</div>
                                </div>
                              )}
                              {ai.adx != null && (
                                <div className="text-center p-2 bg-zinc-800/50 rounded">
                                  <div className="font-mono text-sm font-bold text-zinc-100">
                                    {formatNum(ai.adx, 1)}
                                  </div>
                                  <div className="text-[10px] text-zinc-500">ADX</div>
                                </div>
                              )}
                              {ai.rvol != null && (
                                <div className="text-center p-2 bg-zinc-800/50 rounded">
                                  <div className="font-mono text-sm font-bold text-zinc-100">
                                    {formatNum(ai.rvol, 2)}x
                                  </div>
                                  <div className="text-[10px] text-zinc-500">RVOL</div>
                                </div>
                              )}
                            </div>
                          </>
                        ) : (
                          <p className="text-xs text-zinc-500">
                            No legacy zone metrics recorded for this signal. The ensemble brain
                            decision, narrative, and rules are shown above.
                          </p>
                        )}
                      </div>
                    </div>
                  </>
                ) : (
                  <div className="flex flex-col items-center justify-center py-12 text-center">
                    <Brain className="w-12 h-12 text-zinc-700 mb-3" />
                    <p className="text-sm text-zinc-500">No AI reasoning data available</p>
                  </div>
                )}
              </TabsContent>

              {/* Raw Data Tab */}
              <TabsContent value="raw" className="space-y-4 mt-0">
                <JsonViewer data={signal} title="Full Signal Payload" />
                {ai && <JsonViewer data={ai} title="AI Reasoning Object" />}
              </TabsContent>
            </Tabs>
          </div>
        </ScrollArea>
      </SheetContent>
    </Sheet>
  );
}
