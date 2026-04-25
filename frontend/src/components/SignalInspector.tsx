'use client';

import {
  TradingSignal,
  AIReasoning,
  getSymbol,
  getSide,
  getScore,
  getPnl,
  getNotes,
} from '@/types/trading';
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
  Bug,
  AlertTriangle,
  MessageSquare,
} from 'lucide-react';
import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { fetchAiRunBySignal } from '@/lib/api';
import { AiOperatingLayerPanel } from '@/components/ai/AiOperatingLayerPanel';
import { mapAiRun } from '@/lib/aiRuns';

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
    <div className='flex items-center justify-between py-1.5'>
      <span className='text-[11px] text-muted-foreground uppercase tracking-wider'>
        {label}
      </span>
      <span className={cn('font-mono text-sm text-foreground', valueClass)}>
        {value}
      </span>
    </div>
  );
}

// Boolean indicator component
function BoolIndicator({
  value,
  label,
}: {
  value: boolean | undefined;
  label: string;
}) {
  const isTrue = value === true;
  return (
    <div className='flex items-center gap-2'>
      <div
        className={cn(
          'w-5 h-5 rounded flex items-center justify-center',
          isTrue
            ? 'bg-[var(--to-long)]/20 text-[var(--to-long)]'
            : 'bg-muted text-muted-foreground'
        )}
      >
        {isTrue ? <Check className='w-3 h-3' /> : <X className='w-3 h-3' />}
      </div>
      <span className='text-[11px] text-muted-foreground'>{label}</span>
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
    <div className='flex flex-col gap-1.5'>
      <div className='flex items-center justify-between'>
        <div className='flex items-center gap-1.5'>
          <div className='text-muted-foreground'>{icon}</div>
          <span className='text-[11px] text-muted-foreground'>{label}</span>
        </div>
        <span className='font-mono text-xs text-foreground/90'>
          {value.toFixed(1)}
        </span>
      </div>
      <div className='w-full h-1 bg-muted rounded-full overflow-hidden'>
        <div
          className={cn(
            'h-full rounded-full transition-all',
            getColor(percentage)
          )}
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
    <div className='rounded-lg border border-border bg-card overflow-hidden'>
      <div className='flex items-center justify-between px-3 py-2 border-b border-border bg-muted/40'>
        <span className='text-[11px] text-muted-foreground font-mono uppercase tracking-wider'>
          {title}
        </span>
        <button
          onClick={handleCopy}
          className='flex items-center gap-1 text-[10px] text-muted-foreground hover:text-foreground transition-colors'
        >
          {copied ? (
            <>
              <CheckCircle2 className='w-3 h-3 text-[var(--to-long)]' />
              <span className='text-[var(--to-long)]'>Copied!</span>
            </>
          ) : (
            <>
              <Copy className='w-3 h-3' />
              <span>Copy</span>
            </>
          )}
        </button>
      </div>
      <ScrollArea className='h-64'>
        <pre className='p-3 text-[11px] text-muted-foreground font-mono leading-relaxed whitespace-pre-wrap break-words'>
          {jsonString}
        </pre>
      </ScrollArea>
    </div>
  );
}

// Derive high-level execution plan (action + intended broker behaviour)
// for display in the Signals drawer header.
function deriveExecutionPlan(signal: TradingSignal): {
  actionLabel: string;
  brokerLabel: string;
  description: string;
} {
  const rawAction =
    (signal.signal_action as string | undefined) ??
    (signal.status?.toLowerCase() === 'closed' || signal.exit_type
      ? 'exit'
      : undefined);

  const action = (rawAction || 'entry').toLowerCase();

  const execSource = signal.execution_source || 'signal_only';
  const runMode = (signal.run_mode || signal.mode || '').toString().toUpperCase();

  let brokerLabel = 'Signal-only (no broker execution)';
  if (execSource === 'paper') {
    brokerLabel = 'Paper simulator';
  } else if (execSource === 'metaapi') {
    brokerLabel = 'MetaApi MT5 bridge';
  }

  let description: string;
  switch (action) {
    case 'exit':
      description =
        'Exit → close the existing position on the broker (reduce-only equivalent where supported).';
      break;
    case 'close_all':
      description =
        'Close all → close all open positions for this account and symbol on the active broker.';
      break;
    case 'modify':
      description =
        'Modify → update stop-loss / take-profit on the broker position or cancel+replace where direct modification is unavailable.';
      break;
    case 'cancel':
      description =
        'Cancel → cancel any pending or open position associated with this signal on the broker.';
      break;
    default:
      description =
        'Entry → create a new position via the active execution adapter (market by default).';
      break;
  }

  const modePrefix =
    runMode === 'LIVE'
      ? 'LIVE'
      : runMode === 'PAPER'
        ? 'PAPER'
        : runMode || 'AUTO';

  return {
    actionLabel: action.toUpperCase(),
    brokerLabel: `${modePrefix} · ${brokerLabel}`,
    description,
  };
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

function getRuleBadge(rule: Record<string, unknown>, ai: AIReasoning | null) {
  const ruleId = String(rule?.rule_id || '').toLowerCase();
  const explicitStatus = String(rule?.status || '').toLowerCase();

  if (ruleId === 'llm_context' || ruleId === 'llm_error') {
    const llmStatus =
      explicitStatus || String(ai?.llm_status || '').toLowerCase() || 'skipped';
    if (llmStatus === 'ok') {
      return {
        label: 'OK',
        rowClass: 'border-[var(--to-long)]/20 bg-emerald-500/5',
        textClass: 'text-[var(--to-long)]',
      };
    }
    if (llmStatus === 'error') {
      return {
        label: 'ERROR (NON-BLOCKING)',
        rowClass: 'border-amber-500/25 bg-amber-500/5',
        textClass: 'text-amber-400',
      };
    }
    return {
      label: 'SKIPPED',
      rowClass: 'border-amber-500/25 bg-amber-500/5',
      textClass: 'text-amber-400',
    };
  }

  const passed = rule?.passed === true;
  return {
    label: passed ? 'PASS' : 'FAIL',
    rowClass: passed
      ? 'border-[var(--to-long)]/20 bg-emerald-500/5'
      : 'border-rose-500/20 bg-rose-500/5',
    textClass: passed ? 'text-[var(--to-long)]' : 'text-rose-400',
  };
}

function getRuleDisplayId(rule: Record<string, unknown>): string {
  const rawRuleId = String(rule?.rule_id || 'rule');
  if (rawRuleId.toLowerCase() === 'llm_error') {
    return 'llm_context';
  }
  return rawRuleId;
}

function isPendingAiRun(aiRun: {
  recommendation?: string;
  confidence?: number;
  memo?: string;
  votes?: Record<string, string>;
  transcript?: Array<unknown>;
}): boolean {
  return (
    aiRun.recommendation === 'pending' ||
    (aiRun.confidence === 0 &&
      !aiRun.memo &&
      Object.keys(aiRun.votes || {}).length === 0 &&
      (aiRun.transcript || []).length === 0)
  );
}

function hasAiOperatingLayerData(aiRun: {
  chart_context?: Record<string, unknown>;
  pine_context?: Record<string, unknown>;
  module_status?: Record<string, unknown>;
  layered_output?: Record<string, unknown>;
}): boolean {
  return (
    Object.keys(aiRun.chart_context || {}).length > 0 ||
    Object.keys(aiRun.pine_context || {}).length > 0 ||
    Object.keys(aiRun.module_status || {}).length > 0 ||
    Object.keys(aiRun.layered_output || {}).length > 0
  );
}

export function SignalInspector({
  signal,
  open,
  onOpenChange,
}: SignalInspectorProps) {
  const [showDebug, setShowDebug] = useState(false);
  const signalId = signal?.id ? parseInt(String(signal.id), 10) : null;
  const { data: aiRun, isLoading: aiRunLoading } = useQuery({
    queryKey: ['ai-run', signalId],
    queryFn: () => fetchAiRunBySignal(signalId!),
    enabled: !!signalId && open && !Number.isNaN(signalId),
  });

  if (!signal) return null;

  const symbol = getSymbol(signal);
  const side = getSide(signal);
  const score = getScore(signal);
  const pnl = getPnl(signal);
  const ai = parseAIReasoning(signal);
  const notes = (() => {
    const raw = getNotes(signal);
    if (!raw) return null;
    const trimmed = raw.trim();
    if (
      (trimmed.startsWith('{') && trimmed.endsWith('}')) ||
      trimmed.includes('"error":')
    ) {
      return null;
    }
    return raw;
  })();
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

  const decisionValue = String(
    ai?.decision || signal.status || 'unknown'
  ).toUpperCase();
  const decisionTrace = ai?.decision_trace;
  const traceRules = Array.isArray(decisionTrace?.rules)
    ? decisionTrace?.rules
    : [];
  const failingRules = traceRules.filter((rule) => rule?.passed === false);
  const rejectedRuleMessage =
    (decisionTrace?.rejected_rule as { message?: string } | undefined)
      ?.message ||
    ai?.reason ||
    notes ||
    'No explicit rejection reason was provided.';
  const llmStatus = String(ai?.llm_status || '').toLowerCase();
  const llmContextMessage =
    llmStatus === 'ok' ? null : 'Context unavailable — treated as neutral.';

  const executionPlan = deriveExecutionPlan(signal);

  return (
    <Sheet open={open} onOpenChange={onOpenChange}>
      <SheetContent
        data-testid='signal-inspector-drawer'
        className='w-full sm:max-w-xl bg-background border-border p-0'
        aria-describedby='signal-inspector-desc'
      >
        <SheetDescription id='signal-inspector-desc' className='sr-only'>
          Trade details and AI reasoning
        </SheetDescription>
        <ScrollArea className='h-full'>
          <div className='p-6'>
            {/* Header */}
            <SheetHeader className='mb-6'>
              <div className='flex items-center gap-2 mb-2'>
                <Badge
                  className={cn(
                    'text-xs font-bold px-2.5 py-1 border-0',
                    isBuy
                      ? 'bg-[var(--to-long)]/20 text-[var(--to-long)]'
                      : 'bg-rose-500/20 text-rose-400'
                  )}
                >
                  {side.toUpperCase()}
                </Badge>
                <Badge
                  className={cn(
                    'text-xs px-2 py-0.5 border border-border',
                    signal.status?.toLowerCase() === 'active'
                      ? 'text-blue-400 border-blue-500/30'
                      : signal.status?.toLowerCase() === 'ai_rejected'
                      ? 'text-rose-400 border-rose-500/30'
                      : 'text-muted-foreground'
                  )}
                >
                  {signal.status?.toUpperCase()}
                </Badge>
                {ai?.is_accuracy && (
                  <Badge className='text-xs px-2 py-0.5 border-0 bg-purple-500/20 text-purple-400'>
                    ACCURACY
                  </Badge>
                )}
              </div>
              <SheetTitle className='flex items-baseline gap-2 text-left'>
                <span className='font-mono text-2xl font-bold text-foreground'>
                  {symbol}
                </span>
                {entryPrice && (
                  <span className='font-mono text-lg text-muted-foreground'>
                    @
                    {formatNum(
                      entryPrice,
                      symbol.includes('JPY')
                        ? 3
                        : symbol.includes('BTC')
                        ? 2
                        : 5
                    )}
                  </span>
                )}
              </SheetTitle>
              <p className='text-xs text-muted-foreground font-mono'>
                {format(new Date(signal.created_at), 'PPpp')}
              </p>
            </SheetHeader>

            {/* Execution plan summary */}
            <div className='mb-4 rounded-lg bg-card border border-border px-4 py-3 space-y-1.5'>
              <div className='flex items-center justify-between gap-2'>
                <span className='text-[11px] text-muted-foreground uppercase tracking-wider'>
                  Execution Plan
                </span>
                <Badge className='text-[10px] px-2 py-0.5 border-0 bg-muted text-muted-foreground'>
                  {executionPlan.brokerLabel}
                </Badge>
              </div>
              <div className='flex items-center justify-between gap-2'>
                <span className='font-mono text-xs font-semibold text-foreground'>
                  {executionPlan.actionLabel}
                </span>
              </div>
              <p className='text-[11px] text-muted-foreground leading-relaxed'>
                {executionPlan.description}
              </p>
            </div>

            {/* Tabs */}
            <Tabs defaultValue='overview' className='w-full'>
              <TabsList className='w-full bg-card border border-border p-1 mb-4'>
                <TabsTrigger
                  value='overview'
                  className='flex-1 data-[state=active]:bg-muted text-xs font-mono uppercase'
                >
                  <Activity className='w-3 h-3 mr-1.5' />
                  Overview
                </TabsTrigger>
                <TabsTrigger
                  value='ai'
                  className='flex-1 data-[state=active]:bg-muted text-xs font-mono uppercase'
                >
                  <Brain className='w-3 h-3 mr-1.5' />
                  AI Brain
                </TabsTrigger>
                <TabsTrigger
                  value='ai-memo'
                  className='flex-1 data-[state=active]:bg-muted text-xs font-mono uppercase'
                >
                  <MessageSquare className='w-3 h-3 mr-1.5' />
                  AI Memo
                </TabsTrigger>
                <TabsTrigger
                  value='raw'
                  className='flex-1 data-[state=active]:bg-muted text-xs font-mono uppercase'
                >
                  <Code2 className='w-3 h-3 mr-1.5' />
                  Raw Data
                </TabsTrigger>
              </TabsList>

              {/* Overview Tab */}
              <TabsContent value='overview' className='space-y-4 mt-0'>
                {/* AI Reasoning / Notes */}
                {notes && (
                  <div className='p-3 rounded-lg bg-card border border-border'>
                    <div className='flex items-center gap-2 mb-2'>
                      <FileText className='w-4 h-4 text-muted-foreground' />
                      <span className='text-[11px] text-muted-foreground uppercase tracking-wider'>
                        AI Reasoning
                      </span>
                    </div>
                    <p className='text-sm text-foreground/90 leading-relaxed'>
                      {notes}
                    </p>
                  </div>
                )}

                {/* Filter/Rejection Reason */}
                {signal.filter_reason &&
                  signal.status?.toLowerCase() !== 'active' && (
                    <div className='p-3 rounded-lg bg-amber-500/10 border border-amber-500/20'>
                      <div className='flex items-center gap-2 mb-1'>
                        <Shield className='w-4 h-4 text-amber-400' />
                        <span className='text-[11px] font-semibold text-amber-400 uppercase'>
                          Filter Reason
                        </span>
                      </div>
                      <p className='text-sm text-amber-200/80'>
                        {signal.filter_reason}
                      </p>
                    </div>
                  )}

                {/* Technical Setup */}
                <div className='rounded-lg bg-card border border-border overflow-hidden'>
                  <div className='px-4 py-2.5 border-b border-border flex items-center gap-2'>
                    <Target className='w-4 h-4 text-muted-foreground' />
                    <span className='text-[11px] text-muted-foreground uppercase tracking-wider'>
                      Technical Setup
                    </span>
                  </div>
                  <div className='p-4 space-y-1'>
                    {entryPrice && (
                      <InfoRow
                        label='Entry'
                        value={`$${formatNum(entryPrice, 5)}`}
                      />
                    )}
                    {stopLoss && (
                      <InfoRow
                        label='Stop Loss'
                        value={`$${formatNum(stopLoss, 5)}`}
                        valueClass='text-rose-400'
                      />
                    )}
                    {takeProfit && (
                      <InfoRow
                        label='Take Profit'
                        value={`$${formatNum(takeProfit, 5)}`}
                        valueClass='text-[var(--to-long)]'
                      />
                    )}
                    <Separator className='my-2 bg-border' />
                    {signal.position_size && (
                      <InfoRow
                        label='Position Size'
                        value={`${signal.position_size} lots`}
                      />
                    )}
                    {signal.rr_ratio && (
                      <InfoRow
                        label='Risk:Reward'
                        value={`1:${formatNum(signal.rr_ratio, 2)}`}
                      />
                    )}
                    {signal.sl_pips && (
                      <InfoRow
                        label='SL Distance'
                        value={`${formatNum(signal.sl_pips, 1)} ${
                          /NAS|US30|SPX|UK100|GER|FRA|JPN225|AUS200|NDX|USTEC/.test(symbol?.toUpperCase() ?? '')
                            ? 'pts'
                            : 'pips'
                        }`}
                      />
                    )}

                    {/* PnL Section */}
                    {pnl !== null && (
                      <>
                        <Separator className='my-2 bg-border' />
                        <InfoRow
                          label='Realized PnL'
                          value={`${pnl >= 0 ? '+' : ''}$${formatNum(pnl, 2)}`}
                          valueClass={
                            pnl >= 0 ? 'text-[var(--to-long)]' : 'text-rose-400'
                          }
                        />
                        {signal.pnl_percentage != null && (
                          <InfoRow
                            label='PnL %'
                            value={`${
                              signal.pnl_percentage >= 0 ? '+' : ''
                            }${formatNum(signal.pnl_percentage, 2)}%`}
                            valueClass={
                              signal.pnl_percentage >= 0
                                ? 'text-[var(--to-long)]'
                                : 'text-rose-400'
                            }
                          />
                        )}
                        {signal.exit_type && (
                          <InfoRow
                            label='Exit Type'
                            value={signal.exit_type.replace('_', ' ')}
                          />
                        )}
                      </>
                    )}
                  </div>
                </div>

                {/* AI Confidence */}
                {score !== null && (
                  <div className='rounded-lg bg-card border border-border p-4'>
                    <div className='flex items-center justify-between mb-2'>
                      <span className='text-[11px] text-muted-foreground uppercase tracking-wider'>
                        AI Confidence
                      </span>
                      <span
                        className={cn(
                          'font-mono text-2xl font-bold',
                          score >= 70
                            ? 'text-[var(--to-long)]'
                            : score >= 50
                            ? 'text-amber-400'
                            : 'text-rose-400'
                        )}
                      >
                        {score}%
                      </span>
                    </div>
                    <div className='w-full h-2 bg-muted rounded-full overflow-hidden'>
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
              <TabsContent value='ai' className='space-y-4 mt-0'>
                {ai ? (
                  <>
                    {/* Ensemble Decision Summary */}
                    <div className='rounded-lg bg-card border border-border overflow-hidden'>
                      <div className='px-4 py-2.5 border-b border-border flex items-center gap-2'>
                        <Shield className='w-4 h-4 text-muted-foreground' />
                        <span className='text-[11px] text-muted-foreground uppercase tracking-wider'>
                          Ensemble Decision
                        </span>
                      </div>
                      <div className='p-4 space-y-4'>
                        <div className='flex items-start justify-between gap-3'>
                          <div>
                            <div className='text-[11px] text-muted-foreground uppercase tracking-wider mb-1'>
                              Decision Summary
                            </div>
                            <div className='text-sm text-foreground/90'>
                              {decisionValue === 'GO'
                                ? 'Approved: all active gates passed.'
                                : decisionValue === 'MODEL_ERROR'
                                ? `Model error: ${rejectedRuleMessage}`
                                : `Rejected: ${rejectedRuleMessage}`}
                            </div>
                          </div>
                          <span
                            className={cn(
                              'font-mono text-sm font-bold px-2.5 py-1 rounded',
                              decisionValue === 'GO' &&
                                'bg-[var(--to-long)]/20 text-[var(--to-long)]',
                              decisionValue === 'NO_GO' &&
                                'bg-rose-500/20 text-rose-400',
                              decisionValue === 'MODEL_ERROR' &&
                                'bg-amber-500/20 text-amber-400',
                              !['GO', 'NO_GO', 'MODEL_ERROR'].includes(
                                decisionValue
                              ) && 'bg-muted text-muted-foreground'
                            )}
                          >
                            {decisionValue}
                          </span>
                        </div>

                        {decisionTrace?.rf_probability_pct != null &&
                          decisionTrace?.threshold_pct != null && (
                            <div className='text-xs text-muted-foreground'>
                              RF Gate:{' '}
                              {formatNum(decisionTrace.rf_probability_pct, 1)}%
                              {' vs '}
                              {formatNum(decisionTrace.threshold_pct, 1)}%
                              threshold
                            </div>
                          )}

                        {(llmStatus ||
                          traceRules.some(
                            (r) => r?.rule_id === 'llm_context'
                          )) && (
                          <div className='text-xs text-muted-foreground'>
                            LLM Context:{' '}
                            <span
                              className={cn(
                                'font-semibold',
                                llmStatus === 'ok' && 'text-[var(--to-long)]',
                                llmStatus === 'skipped' && 'text-amber-400',
                                llmStatus === 'error' && 'text-amber-400'
                              )}
                            >
                              {llmStatus === 'ok'
                                ? 'OK'
                                : llmStatus === 'error'
                                ? 'ERROR (NON-BLOCKING)'
                                : 'SKIPPED'}
                            </span>
                            {llmContextMessage && (
                              <span className='ml-2'>{llmContextMessage}</span>
                            )}
                          </div>
                        )}

                        {traceRules.length > 0 && (
                          <div className='space-y-2'>
                            <div className='text-[11px] text-muted-foreground uppercase tracking-wider'>
                              Decision Breakdown
                            </div>
                            {(decisionValue === 'NO_GO' &&
                            failingRules.length > 0
                              ? failingRules
                              : traceRules
                            ).map((rule, idx) => {
                              const badge = getRuleBadge(
                                rule as Record<string, unknown>,
                                ai
                              );
                              const ruleMessage =
                                rule?.message != null
                                  ? String(rule.message)
                                  : '';
                              return (
                                 
                                <div
                                  key={`${getRuleDisplayId(
                                    rule as Record<string, unknown>
                                  )}-${idx}`}
                                  className={cn(
                                    'text-xs rounded border px-2.5 py-2 flex items-start justify-between gap-3',
                                    badge.rowClass
                                  )}
                                >
                                  <div>
                                    <div className='font-mono text-foreground/90'>
                                      {getRuleDisplayId(
                                        rule as Record<string, unknown>
                                      )}
                                    </div>
                                    {ruleMessage && (
                                      <div className='text-muted-foreground mt-0.5'>
                                        {ruleMessage}
                                      </div>
                                    )}
                                  </div>
                                  <div
                                    className={cn(
                                      'text-[10px] font-semibold uppercase whitespace-nowrap',
                                      badge.textClass
                                    )}
                                  >
                                    {badge.label}
                                  </div>
                                </div>
                              );
                            })}
                          </div>
                        )}

                        {ai.narrative && (
                          <div className='text-xs text-muted-foreground leading-relaxed'>
                            <span className='block text-[11px] text-muted-foreground uppercase tracking-wider mb-1'>
                              Market Narrative
                            </span>
                            <p>{ai.narrative}</p>
                          </div>
                        )}

                        {Array.isArray(ai.rules) && ai.rules.length > 0 && (
                          <div className='text-xs text-foreground/90'>
                            <span className='block text-[11px] text-muted-foreground uppercase tracking-wider mb-1'>
                              RAG Rules (Top {Math.min(ai.rules.length, 5)})
                            </span>
                            <ul className='list-disc pl-4 space-y-1'>
                              {ai.rules.slice(0, 5).map((rule, idx) => (
                                 
                                <li key={idx}>{String(rule)}</li>
                              ))}
                            </ul>
                          </div>
                        )}

                        <button
                          type='button'
                          onClick={() => setShowDebug((v) => !v)}
                          className='inline-flex items-center gap-2 text-xs text-muted-foreground hover:text-foreground transition-colors'
                        >
                          <Bug className='w-3.5 h-3.5' />
                          {showDebug ? 'Hide Debug' : 'Show Debug'}
                        </button>

                        {showDebug && (
                          <div className='space-y-2 rounded border border-border bg-background/50 p-3'>
                            <div className='inline-flex items-center gap-1.5 text-[11px] uppercase tracking-wider text-amber-400'>
                              <AlertTriangle className='w-3 h-3' />
                              Debug View (Dev)
                            </div>
                            <JsonViewer
                              data={{
                                rf_prob: ai.rf_prob,
                                rf_threshold: ai.rf_threshold,
                                llm_status: ai.llm_status,
                                llm_model_used: ai.llm_model_used,
                                llm_error_code: ai.llm_error_code,
                                llm_error_message_short:
                                  ai.llm_error_message_short,
                                decision_trace: ai.decision_trace,
                              }}
                              title='Model Output'
                            />
                            {ai.llm_error_raw && (
                              <JsonViewer
                                data={ai.llm_error_raw}
                                title='LLM Raw Error (Debug Only)'
                              />
                            )}
                            <JsonViewer
                              data={ai.decision_trace?.features_snapshot || {}}
                              title='Feature Snapshot'
                            />
                          </div>
                        )}
                      </div>
                    </div>

                    {/* Zone Analysis */}
                    <div className='rounded-lg bg-card border border-border overflow-hidden'>
                      <div className='px-4 py-2.5 border-b border-border flex items-center gap-2'>
                        <BarChart3 className='w-4 h-4 text-muted-foreground' />
                        <span className='text-[11px] text-muted-foreground uppercase tracking-wider'>
                          Zone Analysis
                        </span>
                      </div>
                      <div className='p-4 grid grid-cols-2 gap-4'>
                        <div>
                          {ai.zone_id && (
                            <InfoRow label='Zone ID' value={`#${ai.zone_id}`} />
                          )}
                          {ai.zone_type && (
                            <InfoRow
                              label='Type'
                              value={
                                <Badge
                                  className={cn(
                                    'text-[10px] border-0 px-1.5 py-0',
                                    ai.zone_type === 'demand'
                                      ? 'bg-[var(--to-long)]/20 text-[var(--to-long)]'
                                      : 'bg-rose-500/20 text-rose-400'
                                  )}
                                >
                                  {ai.zone_type.toUpperCase()}
                                </Badge>
                              }
                            />
                          )}
                          {ai.zone_grade && (
                            <InfoRow label='Grade' value={ai.zone_grade} />
                          )}
                        </div>
                        <div>
                          {ai.entry_model && (
                            <InfoRow
                              label='Entry Model'
                              value={ai.entry_model}
                            />
                          )}
                          {ai.session != null && (
                            <InfoRow
                              label='Session'
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
                              label='Trend'
                              value={
                                <div className='flex items-center gap-1'>
                                  {ai.trend === 1 ? (
                                    <>
                                      <TrendingUp className='w-3 h-3 text-[var(--to-long)]' />
                                      <span className='text-[var(--to-long)]'>
                                        Up
                                      </span>
                                    </>
                                  ) : (
                                    <>
                                      <TrendingDown className='w-3 h-3 text-rose-400' />
                                      <span className='text-rose-400'>
                                        Down
                                      </span>
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
                    <div className='rounded-lg bg-card border border-border overflow-hidden'>
                      <div className='px-4 py-2.5 border-b border-border flex items-center gap-2'>
                        <Droplets className='w-4 h-4 text-muted-foreground' />
                        <span className='text-[11px] text-muted-foreground uppercase tracking-wider'>
                          Liquidity Analysis
                        </span>
                      </div>
                      <div className='p-4 space-y-3'>
                        <div className='grid grid-cols-2 gap-x-6 gap-y-2'>
                          <BoolIndicator
                            value={ai.liquidity_swept}
                            label='Liquidity Swept'
                          />
                          <BoolIndicator
                            value={ai.target_swept}
                            label='Target Swept'
                          />
                          <BoolIndicator
                            value={ai.caused_sweep}
                            label='Caused Sweep'
                          />
                          <BoolIndicator
                            value={ai.guardian_structure_break}
                            label='Structure Break'
                          />
                        </div>
                        <Separator className='bg-border' />
                        <div className='grid grid-cols-2 gap-2'>
                          {(ai.liquidity_distance_pips != null ||
                            ai.liquidity_distance != null) && (
                            <InfoRow
                              label='Distance'
                              value={
                                ai.liquidity_distance_pips != null
                                  ? `${formatNum(
                                      ai.liquidity_distance_pips,
                                      1
                                    )} pips`
                                  : ai.liquidity_distance != null &&
                                    ai.liquidity_distance > 0
                                  ? `~${formatNum(
                                      (1 - ai.liquidity_distance / 100) * 50,
                                      1
                                    )} pips`
                                  : ai.liquidity_distance === 0
                                  ? '>50 pips'
                                  : 'N/A'
                              }
                            />
                          )}
                          {(ai.liquidity_spread_pips != null ||
                            ai.liquidity_spread != null) && (
                            <InfoRow
                              label='Zone Range'
                              value={
                                ai.liquidity_spread_pips != null
                                  ? `${formatNum(
                                      ai.liquidity_spread_pips,
                                      1
                                    )} pips`
                                  : `${formatNum(ai.liquidity_spread!, 1)} pips`
                              }
                            />
                          )}
                        </div>
                      </div>
                    </div>

                    {/* AI Metrics */}
                    <div className='rounded-lg bg-card border border-border overflow-hidden'>
                      <div className='px-4 py-2.5 border-b border-border flex items-center gap-2'>
                        <Brain className='w-4 h-4 text-muted-foreground' />
                        <span className='text-[11px] text-muted-foreground uppercase tracking-wider'>
                          AI Metrics
                        </span>
                      </div>
                      <div className='p-4 space-y-3'>
                        {hasLegacyMetrics ? (
                          <>
                            <ScoreBar
                              label='Zone Score'
                              value={ai.zone_score}
                              icon={<Gauge className='w-3 h-3' />}
                            />
                            <ScoreBar
                              label='Base Quality'
                              value={ai.base_quality}
                              icon={<Activity className='w-3 h-3' />}
                            />
                            <ScoreBar
                              label='Departure Strength'
                              value={ai.departure_strength}
                              icon={<Zap className='w-3 h-3' />}
                            />
                            <ScoreBar
                              label='Return Strength'
                              value={ai.return_strength}
                              icon={<TrendingUp className='w-3 h-3' />}
                            />

                            {/* Indicator Stats */}
                            <Separator className='bg-border' />
                            <div className='grid grid-cols-3 gap-2'>
                              {ai.rsi != null && (
                                <div className='text-center p-2 bg-muted rounded'>
                                  <div className='font-mono text-sm font-bold text-foreground'>
                                    {formatNum(ai.rsi, 1)}
                                  </div>
                                  <div className='text-[10px] text-muted-foreground'>
                                    RSI
                                  </div>
                                </div>
                              )}
                              {ai.adx != null && (
                                <div className='text-center p-2 bg-muted rounded'>
                                  <div className='font-mono text-sm font-bold text-foreground'>
                                    {formatNum(ai.adx, 1)}
                                  </div>
                                  <div className='text-[10px] text-muted-foreground'>
                                    ADX
                                  </div>
                                </div>
                              )}
                              {ai.rvol != null && (
                                <div className='text-center p-2 bg-muted rounded'>
                                  <div className='font-mono text-sm font-bold text-foreground'>
                                    {formatNum(ai.rvol, 2)}x
                                  </div>
                                  <div className='text-[10px] text-muted-foreground'>
                                    RVOL
                                  </div>
                                </div>
                              )}
                            </div>
                          </>
                        ) : (
                          <p className='text-xs text-muted-foreground'>
                            No legacy zone metrics recorded for this signal. The
                            ensemble brain decision, narrative, and rules are
                            shown above.
                          </p>
                        )}
                      </div>
                    </div>
                  </>
                ) : (
                  <div className='flex flex-col items-center justify-center py-12 text-center'>
                    <Brain className='w-12 h-12 text-muted-foreground/70 mb-3' />
                    <p className='text-sm text-muted-foreground'>
                      No AI reasoning data available
                    </p>
                  </div>
                )}
              </TabsContent>

              {/* AI Memo Tab — Sprint 3.3: Debate transcript + final vote */}
              <TabsContent value='ai-memo' className='space-y-4 mt-0'>
                {aiRunLoading ? (
                  <div className='p-4 text-sm text-muted-foreground'>
                    Loading AI Memo…
                  </div>
                ) : aiRun ? (
                  isPendingAiRun(aiRun) ? (
                    <div className='flex flex-col items-center justify-center py-12 text-center gap-3 rounded-lg bg-card border border-border'>
                      <Brain className='w-10 h-10 text-muted-foreground/50' />
                      <p className='text-sm text-muted-foreground'>
                        Council is processing this signal.
                      </p>
                      <p className='text-xs text-muted-foreground/70'>
                        The AI memo will appear once the background council run finishes.
                      </p>
                    </div>
                  ) : (
                  <>
                    {hasAiOperatingLayerData(aiRun) && (
                      <AiOperatingLayerPanel run={mapAiRun(aiRun)} />
                    )}
                    <div className='rounded-lg bg-card border border-border overflow-hidden'>
                      <div className='px-4 py-2.5 border-b border-border flex items-center justify-between'>
                        <span className='text-[11px] text-muted-foreground uppercase tracking-wider'>
                          Final Vote
                        </span>
                        <div className='flex items-center gap-2'>
                          <Badge
                            className={cn(
                              'text-xs font-bold',
                              aiRun.recommendation === 'allow'
                                ? 'bg-[var(--to-long)]/20 text-[var(--to-long)]'
                                : 'bg-rose-500/20 text-rose-400'
                            )}
                          >
                            {aiRun.recommendation.toUpperCase()}
                          </Badge>
                          <span className='font-mono text-sm text-foreground'>
                            {aiRun.confidence}%
                          </span>
                        </div>
                      </div>
                      <div className='p-4 space-y-3'>
                        {aiRun.memo && (
                          <p className='text-sm text-foreground/90 leading-relaxed'>
                            {aiRun.memo}
                          </p>
                        )}
                        {aiRun.reason_codes?.length > 0 && (
                          <div className='flex flex-wrap gap-1'>
                            {aiRun.reason_codes.map((code, i) => (
                              <Badge
                                key={i}
                                variant='outline'
                                className='text-[10px] font-mono'
                              >
                                {code}
                              </Badge>
                            ))}
                          </div>
                        )}
                        {Object.keys(aiRun.votes || {}).length > 0 && (
                          <div className='text-xs'>
                            <span className='text-muted-foreground uppercase tracking-wider'>
                              Agent Votes
                            </span>
                            <div className='mt-1.5 flex flex-wrap gap-2'>
                              {Object.entries(aiRun.votes).map(([agent, vote]) => (
                                <span
                                  key={agent}
                                  className={cn(
                                    'font-mono px-2 py-0.5 rounded border text-[10px]',
                                    vote === 'allow'
                                      ? 'border-[var(--to-long)]/30 bg-[var(--to-long)]/10 text-[var(--to-long)]'
                                      : 'border-rose-500/30 bg-rose-500/10 text-rose-400'
                                  )}
                                >
                                  {agent.replace(/_/g, ' ')}: {vote}
                                </span>
                              ))}
                            </div>
                          </div>
                        )}
                      </div>
                    </div>
                    <div className='rounded-lg bg-card border border-border overflow-hidden'>
                      <div className='px-4 py-2.5 border-b border-border'>
                        <span className='text-[11px] text-muted-foreground uppercase tracking-wider'>
                          Debate Transcript
                        </span>
                      </div>
                      <div className='p-4 space-y-3'>
                        {(aiRun.transcript || []).map((msg, i) => (
                          <div
                            key={i}
                            className={cn(
                              'rounded border px-3 py-2 text-sm',
                              // Legacy debate roles
                              msg.role === 'bull' && 'border-[var(--to-long)]/30 bg-emerald-500/5',
                              msg.role === 'bear' && 'border-rose-500/30 bg-rose-500/5',
                              msg.role === 'risk' && 'border-amber-500/30 bg-amber-500/5',
                              msg.role === 'chair' && 'border-blue-500/30 bg-blue-500/5',
                              // Trading Council roles
                              msg.role === 'market_analyst' && 'border-sky-500/30 bg-sky-500/5',
                              msg.role === 'setup_analyst' && 'border-cyan-500/30 bg-cyan-500/5',
                              msg.role === 'bull_researcher' && 'border-[var(--to-long)]/30 bg-emerald-500/5',
                              msg.role === 'bear_researcher' && 'border-rose-500/30 bg-rose-500/5',
                              msg.role === 'research_manager' && 'border-purple-500/30 bg-purple-500/5',
                              msg.role === 'aggressive_debater' && 'border-orange-500/30 bg-orange-500/5',
                              msg.role === 'conservative_debater' && 'border-blue-500/30 bg-blue-500/5',
                              msg.role === 'neutral_debater' && 'border-zinc-500/30 bg-zinc-500/5',
                              msg.role === 'risk_judge' && 'border-amber-500/30 bg-amber-500/5',
                            )}
                          >
                            <div className='text-[10px] font-mono uppercase text-muted-foreground mb-1 tracking-wider'>
                              {msg.role.replace(/_/g, ' ')}
                            </div>
                            <p className='text-foreground/90 leading-relaxed'>
                              {msg.content}
                            </p>
                          </div>
                        ))}
                      </div>
                    </div>
                  </>
                  )
                ) : (
                  <div className='flex flex-col items-center justify-center py-12 text-center gap-3'>
                    <Brain className='w-10 h-10 text-muted-foreground/50' />
                    <p className='text-sm text-muted-foreground'>
                      No AI Council memo recorded for this signal.
                    </p>
                    <p className='text-xs text-muted-foreground/70'>
                      Council runs automatically after each signal is processed.
                    </p>
                  </div>
                )}
              </TabsContent>

              {/* Raw Data Tab */}
              <TabsContent value='raw' className='space-y-4 mt-0'>
                <JsonViewer data={signal} title='Full Signal Payload' />
                {ai && <JsonViewer data={ai} title='AI Reasoning Object' />}
              </TabsContent>
            </Tabs>
          </div>
        </ScrollArea>
      </SheetContent>
    </Sheet>
  );
}
