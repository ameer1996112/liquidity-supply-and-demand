'use client';

import { useState } from 'react';
import {
  TradingSignal,
  getSymbol,
  getSide,
  getScore,
  getPnl,
  getNotes,
  AIReasoning,
} from '@/types/trading';
import { cn } from '@/lib/utils';
import { format } from 'date-fns';
import { ChevronDown, ExternalLink } from 'lucide-react';
import { PnLText } from '@/components/ui/typography';
import { TradeNoteEditor, TradeNoteIndicator } from './TradeNoteEditor';
import { formatDuration } from './TradeTable';
import { SetupEvidenceCell } from './SetupEvidenceCell';
import { SetupEvidenceDetail } from './SetupEvidenceDetail';
import { SetupScoreBadge } from '@/components/shared/SetupScoreBadge';
import { formatJournalPrice } from './priceFormat';

interface ExpandableTradeRowProps {
  signal: TradingSignal;
  onInspect: (signal: TradingSignal) => void;
}

const statusColors: Record<string, string> = {
  active: 'text-long bg-long/10',
  closed: 'text-text-secondary bg-surface-raised/40',
  executed: 'text-long bg-long/10',
  ai_rejected: 'text-short bg-short/10',
  filtered: 'text-text-dim bg-surface-raised/40',
  pending: 'text-warning bg-warning/10',
  failed: 'text-short bg-short/10',
};

const SESSION_LABELS: Record<number, string> = {
  0: 'Asia',
  1: 'LDN',
  2: 'NY',
  3: 'Off',
};

const SESSION_COLORS: Record<number, string> = {
  0: 'text-blue-accent bg-blue-accent/10',
  1: 'text-long bg-long/10',
  2: 'text-amber bg-amber/10',
  3: 'text-text-dim bg-surface-raised/40',
};

function parseAI(signal: TradingSignal): AIReasoning | null {
  if (!signal.ai_reasoning) return null;
  if (typeof signal.ai_reasoning === 'string') {
    try {
      return JSON.parse(signal.ai_reasoning);
    } catch {
      return null;
    }
  }
  return signal.ai_reasoning as AIReasoning;
}

export function ExpandableTradeRow({ signal, onInspect }: ExpandableTradeRowProps) {
  const [expanded, setExpanded] = useState(false);

  const symbol = getSymbol(signal);
  const side = getSide(signal);
  const score = getScore(signal);
  const pnl = getPnl(signal);
  const notes = getNotes(signal);
  const ai = parseAI(signal);

  const entry = signal.price ?? signal.entry;
  const sl = signal.stop_loss ?? signal.sl;
  const tp = signal.take_profit ?? signal.tp;
  const statusClass =
    statusColors[signal.status?.toLowerCase() || ''] || 'text-[var(--to-text-dim)] bg-[var(--to-surface-raised)]/30';

  // Duration — use opened_at (actual trade fill time) over created_at (signal receipt time)
  const durationMs = signal.closed_at
    ? new Date(signal.closed_at).getTime() - new Date(signal.opened_at || signal.created_at).getTime()
    : -1;
  const durationLabel = formatDuration(durationMs);

  // Zone / model / session from top-level signal fields, AI reasoning as fallback
  const zoneType = signal.zone_type || ai?.zone_type;
  const zoneGrade = signal.zone_grade || ai?.zone_grade;
  const entryModel = signal.entry_model || ai?.entry_model;
  const session = signal.session ?? ai?.session;
  const slPips = signal.sl_pips;
  const trend = signal.trend ?? ai?.trend;
  const hasZoneSetup = Boolean(
    zoneType ||
      zoneGrade ||
      entryModel ||
      entry != null ||
      sl != null ||
      tp != null ||
      score != null,
  );

  return (
    <>
      {/* Main Row */}
      <tr
        className="border-b border-[#2a2e39] hover:bg-[#1e222d]/50 cursor-pointer transition-colors group"
        onClick={() => setExpanded((prev) => !prev)}
      >
        {/* Date */}
        <td className="py-2.5 px-3 font-mono text-[11px] text-[var(--to-text-dim)]">
          {format(new Date(signal.created_at), 'MMM dd HH:mm')}
        </td>

        {/* Symbol + Mode */}
        <td className="py-2.5 px-3">
          <span className="font-mono text-xs font-semibold text-[var(--to-text-primary)]">{symbol}</span>
          {(() => {
            const runMode = (signal.run_mode || signal.mode || '').toUpperCase();
            if (runMode === 'LIVE') {
              return (
                <span className="ml-1.5 font-mono text-[9px] font-bold px-1 py-0.5 rounded bg-short/15 text-short">
                  LIVE
                </span>
              );
            }
            if (runMode === 'PAPER') {
              return (
                <span className="ml-1.5 font-mono text-[9px] font-bold px-1 py-0.5 rounded bg-blue-accent/15 text-blue-accent">
                  PAPER
                </span>
              );
            }
            return null;
          })()}
        </td>

        {/* Side */}
        <td className="py-2.5 px-3">
          <span
            className={cn(
              'font-mono text-[10px] font-bold px-1.5 py-0.5 rounded',
              side === 'buy' ? 'text-long bg-long/10' : 'text-short bg-short/10',
            )}
          >
            {side.toUpperCase()}
          </span>
        </td>

        {/* Status */}
        <td className="py-2.5 px-3">
          <span className={cn('font-mono text-[10px] px-1.5 py-0.5 rounded', statusClass)}>
            {(signal.status || '').toUpperCase().replace('_', ' ')}
          </span>
        </td>

        {/* Account */}
        <td className="py-2.5 px-3">
          {signal.account_name ? (
            <span className="font-mono text-[10px] px-1.5 py-0.5 rounded bg-[var(--to-surface-raised)]/60 text-[var(--to-text-secondary)]">
              {signal.account_name}
            </span>
          ) : (
            <span className="text-[var(--to-text-dim)] text-[11px]">—</span>
          )}
        </td>

        {/* Setup */}
        <td className="py-2.5 px-3">
          <div className="flex items-center gap-1.5">
            <SetupEvidenceCell evidence={signal.setup_evidence} hasZoneSetup={hasZoneSetup} />
            <SetupScoreBadge signal={signal} compact />
          </div>
        </td>

        {/* Zone (type + grade) */}
        <td className="py-2.5 px-3">
          {zoneType ? (
            <span
              className={cn(
                'font-mono text-[10px] px-1.5 py-0.5 rounded',
                zoneType.toLowerCase() === 'demand'
                  ? 'text-long bg-long/10'
                  : 'text-short bg-short/10',
              )}
            >
              {zoneType.toUpperCase().slice(0, 1)}
              {zoneGrade ? ` ${zoneGrade}` : ''}
            </span>
          ) : (
            <span className="text-[var(--to-text-dim)] text-[11px]">--</span>
          )}
        </td>

        {/* Entry Model */}
        <td className="py-2.5 px-3">
          {entryModel ? (
            <span className="font-mono text-[10px] text-text-secondary px-1.5 py-0.5 rounded bg-surface-raised/40">
              {entryModel.toUpperCase()}
            </span>
          ) : (
            <span className="text-[var(--to-text-dim)] text-[11px]">--</span>
          )}
        </td>

        {/* Session */}
        <td className="py-2.5 px-3">
          {session != null ? (
            <span
              className={cn(
                'font-mono text-[10px] px-1.5 py-0.5 rounded',
                SESSION_COLORS[session] || SESSION_COLORS[3],
              )}
            >
              {SESSION_LABELS[session] || '--'}
            </span>
          ) : (
            <span className="text-[var(--to-text-dim)] text-[11px]">--</span>
          )}
        </td>

        {/* Entry / Exit */}
        <td className="py-2.5 px-3 font-mono text-[11px] text-[var(--to-text-dim)]">
          {formatJournalPrice(entry, symbol)}
        </td>
        <td className="py-2.5 px-3 font-mono text-[11px] text-[var(--to-text-dim)]">
          {formatJournalPrice(signal.exit_price, symbol)}
        </td>

        {/* Size */}
        <td className="py-2.5 px-3 font-mono text-[11px] text-[var(--to-text-dim)]">
          {signal.position_size != null ? `${signal.position_size}L` : '--'}
        </td>

        {/* SL Pips */}
        <td className="py-2.5 px-3 font-mono text-[11px] text-[var(--to-text-dim)]">
          {slPips != null ? slPips.toFixed(1) : '--'}
        </td>

        {/* AI Score */}
        <td className="py-2.5 px-3">
          {score != null ? (
            <span
              className={cn(
                'font-mono text-[11px] font-semibold',
                score >= 70 ? 'text-long' : score >= 50 ? 'text-amber' : 'text-short',
              )}
            >
              {score}
            </span>
          ) : (
            <span className="text-[var(--to-text-dim)] text-[11px]">--</span>
          )}
        </td>

        {/* R:R */}
        <td className="py-2.5 px-3 font-mono text-[11px] text-[var(--to-text-dim)]">
          {signal.rr_ratio != null ? `1:${signal.rr_ratio.toFixed(1)}` : '--'}
        </td>

        {/* Duration */}
        <td className="py-2.5 px-3 font-mono text-[11px] text-[var(--to-text-dim)]">
          {durationLabel}
        </td>

        {/* PnL */}
        <td className="py-2.5 px-3">
          {pnl != null ? (
            <PnLText value={pnl} variant="currency" size="sm" />
          ) : (
            <span className="text-[var(--to-text-dim)] text-[11px]">--</span>
          )}
        </td>

        {/* Note indicators */}
        <td className="py-2.5 px-2">
          <TradeNoteIndicator signalId={signal.id} />
        </td>

        {/* Expand chevron */}
        <td className="py-2.5 px-3">
          <ChevronDown
            className={cn(
              'w-3.5 h-3.5 text-[var(--to-text-dim)] transition-transform',
              expanded && 'rotate-180',
            )}
          />
        </td>
      </tr>

      {/* Expanded Detail Row */}
      {expanded && (
        <tr className="border-b border-panel-border bg-[var(--to-surface)]/80">
          <td colSpan={19} className="p-4">
            <div className="grid grid-cols-4 gap-6">
              <div className="space-y-2">
                <span className="text-[10px] text-text-dim uppercase tracking-wider font-medium">
                  Setup Evidence
                </span>
                <SetupEvidenceDetail
                  evidence={signal.setup_evidence}
                  fallback={{
                    symbol,
                    zoneType,
                    zoneGrade,
                    entryModel,
                    session,
                    entry,
                    stopLoss: sl,
                    takeProfit: tp,
                    slPips,
                    score,
                    rrRatio: signal.rr_ratio,
                  }}
                />
                {signal.setup_score != null && (
                  <div className="space-y-1.5 border-t border-[var(--to-border)]/60 pt-2 text-[11px]">
                    <div className="flex justify-between">
                      <span className="text-[var(--to-text-dim)]">Score</span>
                      <SetupScoreBadge signal={signal} />
                    </div>
                    {signal.setup_asset_class && (
                      <div className="flex justify-between">
                        <span className="text-[var(--to-text-dim)]">Class</span>
                        <span className="font-mono text-[var(--to-text-secondary)]">
                          {signal.setup_asset_class.toUpperCase()}
                        </span>
                      </div>
                    )}
                    {signal.setup_sl_band && (
                      <div className="flex justify-between">
                        <span className="text-[var(--to-text-dim)]">SL Band</span>
                        <span className="font-mono text-[var(--to-text-secondary)]">
                          {signal.setup_sl_band}
                        </span>
                      </div>
                    )}
                    {signal.setup_strengths?.length ? (
                      <div>
                        <span className="text-[var(--to-text-dim)]">Strengths</span>
                        <p className="mt-0.5 font-mono text-[var(--to-text-secondary)]">
                          {signal.setup_strengths.slice(0, 3).join(', ')}
                        </p>
                      </div>
                    ) : null}
                    {signal.setup_weaknesses?.length ? (
                      <div>
                        <span className="text-[var(--to-text-dim)]">Watch</span>
                        <p className="mt-0.5 font-mono text-amber-300">
                          {signal.setup_weaknesses.slice(0, 3).join(', ')}
                        </p>
                      </div>
                    ) : null}
                  </div>
                )}
              </div>

              {/* Technical Setup */}
              <div className="space-y-2">
                <span className="text-[10px] text-text-dim uppercase tracking-wider font-medium">
                  Technical Setup
                </span>
                <div className="space-y-1.5 text-[11px]">
                  <div className="flex justify-between">
                    <span className="text-[var(--to-text-dim)]">Entry</span>
                    <span className="font-mono text-[var(--to-text-secondary)]">
                      {formatJournalPrice(entry, symbol)}
                    </span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-[var(--to-text-dim)]">Stop Loss</span>
                    <span className="font-mono text-short">
                      {formatJournalPrice(sl, symbol)}
                    </span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-[var(--to-text-dim)]">Take Profit</span>
                    <span className="font-mono text-long">
                      {formatJournalPrice(tp, symbol)}
                    </span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-[var(--to-text-dim)]">Position Size</span>
                    <span className="font-mono text-[var(--to-text-secondary)]">
                      {signal.position_size ?? '--'} lots
                    </span>
                  </div>
                  {signal.rr_ratio != null && (
                    <div className="flex justify-between">
                      <span className="text-[var(--to-text-dim)]">R:R</span>
                      <span className="font-mono text-[var(--to-text-secondary)]">
                        1:{signal.rr_ratio.toFixed(1)}
                      </span>
                    </div>
                  )}
                  {signal.exit_type && (
                    <div className="flex justify-between">
                      <span className="text-[var(--to-text-dim)]">Exit Type</span>
                      <span className="font-mono text-[var(--to-text-secondary)]">
                        {signal.exit_type.replace('_', ' ')}
                      </span>
                    </div>
                  )}
                  {signal.mode && (
                    <div className="flex justify-between">
                      <span className="text-[var(--to-text-dim)]">Mode</span>
                      <span
                        className={cn(
                          'font-mono',
                          signal.mode === 'LIVE' ? 'text-[var(--to-long)]' : 'text-amber-400',
                        )}
                      >
                        {signal.mode}
                      </span>
                    </div>
                  )}
                </div>
              </div>

              {/* AI Analysis */}
              <div className="space-y-2">
                <span className="text-[10px] text-text-dim uppercase tracking-wider font-medium">
                  AI Analysis
                </span>
                <div className="space-y-1.5 text-[11px]">
                  {zoneType && (
                    <div className="flex justify-between">
                      <span className="text-[var(--to-text-dim)]">Zone</span>
                      <span
                        className={cn(
                          'font-mono',
                          zoneType.toLowerCase() === 'demand' ? 'text-long' : 'text-short',
                        )}
                      >
                        {zoneType.toUpperCase()} {zoneGrade || ''}
                      </span>
                    </div>
                  )}
                  {entryModel && (
                    <div className="flex justify-between">
                      <span className="text-[var(--to-text-dim)]">Model</span>
                      <span className="font-mono text-[var(--to-text-secondary)]">
                        {entryModel.toUpperCase()}
                      </span>
                    </div>
                  )}
                  {ai?.decision && (
                    <div className="flex justify-between">
                      <span className="text-[var(--to-text-dim)]">Decision</span>
                      <span
                        className={cn(
                          'font-mono font-semibold',
                          ai.decision === 'GO' ? 'text-long' : 'text-short',
                        )}
                      >
                        {ai.decision}
                      </span>
                    </div>
                  )}
                  {ai?.rf_prob != null && (
                    <div className="flex justify-between">
                      <span className="text-[var(--to-text-dim)]">RF Prob</span>
                      <span
                        className={cn(
                          'font-mono font-semibold',
                          ai.rf_prob >= 0.7
                            ? 'text-long'
                            : ai.rf_prob >= 0.5
                              ? 'text-amber'
                              : 'text-short',
                        )}
                      >
                        {(ai.rf_prob * 100).toFixed(1)}%
                      </span>
                    </div>
                  )}
                  {(signal.liq_swept != null || ai?.liquidity_swept != null) && (
                    <div className="flex justify-between">
                      <span className="text-[var(--to-text-dim)]">Liq Swept</span>
                      <span
                        className={cn(
                          'font-mono',
                          (signal.liq_swept ?? ai?.liquidity_swept) ? 'text-long' : 'text-short',
                        )}
                      >
                        {(signal.liq_swept ?? ai?.liquidity_swept) ? 'YES' : 'NO'}
                      </span>
                    </div>
                  )}
                  {trend != null && (
                    <div className="flex justify-between">
                      <span className="text-[var(--to-text-dim)]">Trend</span>
                      <span
                        className={cn('font-mono', trend === 1 ? 'text-long' : 'text-short')}
                      >
                        {trend === 1 ? 'BULL' : 'BEAR'}
                      </span>
                    </div>
                  )}
                  {signal.rsi != null && (
                    <div className="flex justify-between">
                      <span className="text-[var(--to-text-dim)]">RSI</span>
                      <span
                        className={cn(
                          'font-mono text-[var(--to-text-secondary)]',
                          signal.rsi > 70
                            ? 'text-short'
                            : signal.rsi < 30
                              ? 'text-long'
                              : '',
                        )}
                      >
                        {signal.rsi.toFixed(1)}
                      </span>
                    </div>
                  )}
                  {notes && (
                    <p className="text-[var(--to-text-dim)] text-[11px] leading-relaxed mt-2 line-clamp-3">
                      {notes}
                    </p>
                  )}
                </div>
              </div>

              {/* Execution */}
              <div className="space-y-2">
                <span className="text-[10px] text-text-dim uppercase tracking-wider font-medium">
                  Execution
                </span>
                <div className="space-y-1.5 text-[11px]">
                  <div className="flex justify-between">
                    <span className="text-[var(--to-text-dim)]">Created</span>
                    <span className="font-mono text-[var(--to-text-secondary)]">
                      {format(new Date(signal.created_at), 'MMM dd, HH:mm:ss')}
                    </span>
                  </div>
                  {signal.closed_at && (
                    <div className="flex justify-between">
                      <span className="text-[var(--to-text-dim)]">Closed</span>
                      <span className="font-mono text-[var(--to-text-secondary)]">
                        {format(new Date(signal.closed_at), 'MMM dd, HH:mm:ss')}
                      </span>
                    </div>
                  )}
                  {durationMs > 0 && (
                    <div className="flex justify-between">
                      <span className="text-[var(--to-text-dim)]">Duration</span>
                      <span className="font-mono text-[var(--to-text-secondary)]">{durationLabel}</span>
                    </div>
                  )}
                  {pnl != null && (
                    <div className="flex justify-between">
                      <span className="text-[var(--to-text-dim)]">Profit (MT5)</span>
                      <span className="font-mono font-semibold">
                        <PnLText value={pnl} variant="currency" size="sm" />
                      </span>
                    </div>
                  )}
                  {signal.commission != null && signal.commission !== 0 && (
                    <div className="flex justify-between">
                      <span className="text-[var(--to-text-dim)]">Commission</span>
                      <span className="font-mono text-[var(--to-short)]">
                        ${signal.commission.toFixed(2)}
                      </span>
                    </div>
                  )}
                  {signal.pnl_percentage != null && (
                    <div className="flex justify-between">
                      <span className="text-[var(--to-text-dim)]">PnL %</span>
                      <span
                        className={cn(
                          'font-mono',
                          signal.pnl_percentage >= 0 ? 'text-long' : 'text-short',
                        )}
                      >
                        {signal.pnl_percentage >= 0 ? '+' : ''}
                        {signal.pnl_percentage.toFixed(2)}%
                      </span>
                    </div>
                  )}
                </div>
                <button
                  onClick={(e) => {
                    e.stopPropagation();
                    onInspect(signal);
                  }}
                  className="mt-3 flex items-center gap-1.5 text-[10px] text-[var(--to-text-dim)] hover:text-[var(--to-text-secondary)] transition-colors font-mono"
                >
                  <ExternalLink className="w-3 h-3" />
                  Full Inspector
                </button>
              </div>

              {/* My Notes — TradeNoteEditor */}
              <div
                className="rounded-xl border border-[var(--to-border)] bg-[var(--to-surface-raised)] overflow-hidden"
                onClick={(e) => e.stopPropagation()}
              >
                <TradeNoteEditor signal={signal} compact />
              </div>

            </div>
          </td>
        </tr>
      )}
    </>
  );
}
