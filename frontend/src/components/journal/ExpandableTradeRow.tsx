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
    statusColors[signal.status?.toLowerCase() || ''] || 'text-zinc-400 bg-zinc-700/30';

  // Zone / model / session from top-level signal fields, AI reasoning as fallback
  const zoneType = signal.zone_type || ai?.zone_type;
  const zoneGrade = signal.zone_grade || ai?.zone_grade;
  const entryModel = signal.entry_model || ai?.entry_model;
  const session = signal.session ?? ai?.session;
  const slPips = signal.sl_pips;
  const trend = signal.trend ?? ai?.trend;

  return (
    <>
      {/* Main Row */}
      <tr
        className="border-b border-[#2a2e39] hover:bg-[#1e222d]/50 cursor-pointer transition-colors group"
        onClick={() => setExpanded((prev) => !prev)}
      >
        {/* Date */}
        <td className="py-2.5 px-3 font-mono text-[11px] text-zinc-500">
          {format(new Date(signal.created_at), 'MMM dd HH:mm')}
        </td>

        {/* Symbol + Mode */}
        <td className="py-2.5 px-3">
          <span className="font-mono text-xs font-semibold text-zinc-200">{symbol}</span>
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
          <span className="font-mono text-[10px] text-zinc-400">
            {signal.account_name ?? 'Unknown'}
          </span>
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
            <span className="text-zinc-600 text-[11px]">--</span>
          )}
        </td>

        {/* Entry Model */}
        <td className="py-2.5 px-3">
          {entryModel ? (
            <span className="font-mono text-[10px] text-text-secondary px-1.5 py-0.5 rounded bg-surface-raised/40">
              {entryModel.toUpperCase()}
            </span>
          ) : (
            <span className="text-zinc-600 text-[11px]">--</span>
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
            <span className="text-zinc-600 text-[11px]">--</span>
          )}
        </td>

        {/* Entry / Exit */}
        <td className="py-2.5 px-3 font-mono text-[11px] text-zinc-400">
          {entry != null
            ? entry.toFixed(
                symbol.includes('JPY')
                  ? 3
                  : symbol.includes('BTC') || symbol.includes('XAU')
                    ? 2
                    : 5,
              )
            : '--'}
        </td>
        <td className="py-2.5 px-3 font-mono text-[11px] text-zinc-400">
          {signal.exit_price != null
            ? signal.exit_price.toFixed(
                symbol.includes('JPY')
                  ? 3
                  : symbol.includes('BTC') || symbol.includes('XAU')
                    ? 2
                    : 5,
              )
            : '--'}
        </td>

        {/* SL Pips */}
        <td className="py-2.5 px-3 font-mono text-[11px] text-zinc-400">
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
            <span className="text-zinc-600 text-[11px]">--</span>
          )}
        </td>

        {/* R:R */}
        <td className="py-2.5 px-3 font-mono text-[11px] text-zinc-400">
          {signal.rr_ratio != null ? `1:${signal.rr_ratio.toFixed(1)}` : '--'}
        </td>

        {/* PnL */}
        <td className="py-2.5 px-3">
          {pnl != null ? (
            <PnLText value={pnl} variant="currency" size="sm" />
          ) : (
            <span className="text-zinc-600 text-[11px]">--</span>
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
              'w-3.5 h-3.5 text-zinc-600 transition-transform',
              expanded && 'rotate-180',
            )}
          />
        </td>
      </tr>

      {/* Expanded Detail Row */}
      {expanded && (
        <tr className="border-b border-panel-border bg-[var(--to-surface)]/80">
          <td colSpan={16} className="p-4">
            <div className="grid grid-cols-4 gap-6">
              {/* Technical Setup */}
              <div className="space-y-2">
                <span className="text-[10px] text-text-dim uppercase tracking-wider font-medium">
                  Technical Setup
                </span>
                <div className="space-y-1.5 text-[11px]">
                  <div className="flex justify-between">
                    <span className="text-zinc-500">Entry</span>
                    <span className="font-mono text-zinc-300">
                      <PnLText value={entry ?? null} variant="currency" size="sm" />
                    </span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-zinc-500">Stop Loss</span>
                    <span className="font-mono text-short">
                      <PnLText value={sl ?? null} variant="currency" size="sm" />
                    </span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-zinc-500">Take Profit</span>
                    <span className="font-mono text-long">
                      <PnLText value={tp ?? null} variant="currency" size="sm" />
                    </span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-zinc-500">Position Size</span>
                    <span className="font-mono text-zinc-300">
                      {signal.position_size ?? '--'} lots
                    </span>
                  </div>
                  {signal.rr_ratio != null && (
                    <div className="flex justify-between">
                      <span className="text-zinc-500">R:R</span>
                      <span className="font-mono text-zinc-300">
                        1:{signal.rr_ratio.toFixed(1)}
                      </span>
                    </div>
                  )}
                  {signal.exit_type && (
                    <div className="flex justify-between">
                      <span className="text-zinc-500">Exit Type</span>
                      <span className="font-mono text-zinc-300">
                        {signal.exit_type.replace('_', ' ')}
                      </span>
                    </div>
                  )}
                  {signal.mode && (
                    <div className="flex justify-between">
                      <span className="text-zinc-500">Mode</span>
                      <span
                        className={cn(
                          'font-mono',
                          signal.mode === 'LIVE' ? 'text-emerald-400' : 'text-amber-400',
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
                      <span className="text-zinc-500">Zone</span>
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
                      <span className="text-zinc-500">Model</span>
                      <span className="font-mono text-zinc-300">
                        {entryModel.toUpperCase()}
                      </span>
                    </div>
                  )}
                  {ai?.decision && (
                    <div className="flex justify-between">
                      <span className="text-zinc-500">Decision</span>
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
                      <span className="text-zinc-500">RF Prob</span>
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
                      <span className="text-zinc-500">Liq Swept</span>
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
                      <span className="text-zinc-500">Trend</span>
                      <span
                        className={cn('font-mono', trend === 1 ? 'text-long' : 'text-short')}
                      >
                        {trend === 1 ? 'BULL' : 'BEAR'}
                      </span>
                    </div>
                  )}
                  {signal.rsi != null && (
                    <div className="flex justify-between">
                      <span className="text-zinc-500">RSI</span>
                      <span
                        className={cn(
                          'font-mono text-zinc-300',
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
                    <p className="text-zinc-400 text-[11px] leading-relaxed mt-2 line-clamp-3">
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
                    <span className="text-zinc-500">Created</span>
                    <span className="font-mono text-zinc-300">
                      {format(new Date(signal.created_at), 'MMM dd, HH:mm:ss')}
                    </span>
                  </div>
                  {signal.closed_at && (
                    <div className="flex justify-between">
                      <span className="text-zinc-500">Closed</span>
                      <span className="font-mono text-zinc-300">
                        {format(new Date(signal.closed_at), 'MMM dd, HH:mm:ss')}
                      </span>
                    </div>
                  )}
                  {pnl != null && (
                    <div className="flex justify-between">
                      <span className="text-zinc-500">PnL</span>
                      <span className="font-mono font-semibold">
                        <PnLText value={pnl} variant="currency" size="sm" />
                      </span>
                    </div>
                  )}
                  {signal.pnl_percentage != null && (
                    <div className="flex justify-between">
                      <span className="text-zinc-500">PnL %</span>
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
                  className="mt-3 flex items-center gap-1.5 text-[10px] text-zinc-500 hover:text-zinc-300 transition-colors font-mono"
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

