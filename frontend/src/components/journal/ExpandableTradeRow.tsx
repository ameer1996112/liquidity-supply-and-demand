'use client';

import { useState } from 'react';
import { TradingSignal, getSymbol, getSide, getScore, getPnl, getNotes, AIReasoning } from '@/types/trading';
import { cn } from '@/lib/utils';
import { format } from 'date-fns';
import { ChevronDown, ExternalLink } from 'lucide-react';

interface ExpandableTradeRowProps {
  signal: TradingSignal;
  onInspect: (signal: TradingSignal) => void;
}

const statusColors: Record<string, string> = {
  active: 'text-blue-400 bg-blue-500/10',
  closed: 'text-zinc-300 bg-zinc-700/30',
  executed: 'text-emerald-400 bg-emerald-500/10',
  ai_rejected: 'text-rose-400 bg-rose-500/10',
  filtered: 'text-amber-400 bg-amber-500/10',
  pending: 'text-zinc-400 bg-zinc-700/30',
  failed: 'text-red-400 bg-red-500/10',
};

function parseAI(signal: TradingSignal): AIReasoning | null {
  if (!signal.ai_reasoning) return null;
  if (typeof signal.ai_reasoning === 'string') {
    try { return JSON.parse(signal.ai_reasoning); } catch { return null; }
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
  const statusClass = statusColors[signal.status?.toLowerCase() || ''] || 'text-zinc-400 bg-zinc-700/30';

  return (
    <>
      {/* Main Row */}
      <tr
        className="border-b border-[#2a2e39] hover:bg-[#1e222d]/50 cursor-pointer transition-colors group"
        onClick={() => setExpanded(!expanded)}
      >
        <td className="py-2.5 px-3 font-mono text-[11px] text-zinc-500">
          {format(new Date(signal.created_at), 'MMM dd HH:mm')}
        </td>
        <td className="py-2.5 px-3">
          <span className="font-mono text-xs font-semibold text-zinc-200">{symbol}</span>
        </td>
        <td className="py-2.5 px-3">
          <span
            className={cn(
              'font-mono text-[10px] font-bold px-1.5 py-0.5 rounded',
              side === 'buy' ? 'text-emerald-400 bg-emerald-500/10' : 'text-rose-400 bg-rose-500/10'
            )}
          >
            {side.toUpperCase()}
          </span>
        </td>
        <td className="py-2.5 px-3">
          <span className={cn('font-mono text-[10px] px-1.5 py-0.5 rounded', statusClass)}>
            {(signal.status || '').toUpperCase().replace('_', ' ')}
          </span>
        </td>
        <td className="py-2.5 px-3 font-mono text-[11px] text-zinc-400">
          {entry != null ? entry.toFixed(symbol.includes('JPY') ? 3 : symbol.includes('BTC') || symbol.includes('XAU') ? 2 : 5) : '--'}
        </td>
        <td className="py-2.5 px-3 font-mono text-[11px] text-zinc-400">
          {signal.exit_price != null ? signal.exit_price.toFixed(symbol.includes('JPY') ? 3 : symbol.includes('BTC') || symbol.includes('XAU') ? 2 : 5) : '--'}
        </td>
        <td className="py-2.5 px-3">
          {score != null ? (
            <span
              className={cn(
                'font-mono text-[11px] font-semibold',
                score >= 70 ? 'text-emerald-400' : score >= 50 ? 'text-amber-400' : 'text-rose-400'
              )}
            >
              {score}
            </span>
          ) : (
            <span className="text-zinc-600 text-[11px]">--</span>
          )}
        </td>
        <td className="py-2.5 px-3 font-mono text-[11px] text-zinc-400">
          {signal.rr_ratio != null ? `1:${signal.rr_ratio.toFixed(1)}` : '--'}
        </td>
        <td className="py-2.5 px-3">
          {pnl != null ? (
            <span
              className={cn(
                'font-mono text-[11px] font-semibold',
                pnl > 0 ? 'text-emerald-400' : pnl < 0 ? 'text-rose-400' : 'text-zinc-400'
              )}
            >
              {pnl >= 0 ? '+' : ''}${pnl.toFixed(2)}
            </span>
          ) : (
            <span className="text-zinc-600 text-[11px]">--</span>
          )}
        </td>
        <td className="py-2.5 px-3">
          <ChevronDown
            className={cn(
              'w-3.5 h-3.5 text-zinc-600 transition-transform',
              expanded && 'rotate-180'
            )}
          />
        </td>
      </tr>

      {/* Expanded Detail Row */}
      {expanded && (
        <tr className="border-b border-[#2a2e39] bg-[#1a1e28]">
          <td colSpan={10} className="p-4">
            <div className="grid grid-cols-3 gap-6">
              {/* Technical Setup */}
              <div className="space-y-2">
                <span className="text-[10px] text-zinc-500 uppercase tracking-wider font-medium">
                  Technical Setup
                </span>
                <div className="space-y-1.5 text-[11px]">
                  <div className="flex justify-between">
                    <span className="text-zinc-500">Entry</span>
                    <span className="font-mono text-zinc-300">{entry != null ? `$${entry}` : '--'}</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-zinc-500">Stop Loss</span>
                    <span className="font-mono text-rose-400">{sl != null ? `$${sl}` : '--'}</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-zinc-500">Take Profit</span>
                    <span className="font-mono text-emerald-400">{tp != null ? `$${tp}` : '--'}</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-zinc-500">Position Size</span>
                    <span className="font-mono text-zinc-300">{signal.position_size ?? '--'} lots</span>
                  </div>
                  {signal.exit_type && (
                    <div className="flex justify-between">
                      <span className="text-zinc-500">Exit Type</span>
                      <span className="font-mono text-zinc-300">{signal.exit_type.replace('_', ' ')}</span>
                    </div>
                  )}
                  {signal.mode && (
                    <div className="flex justify-between">
                      <span className="text-zinc-500">Mode</span>
                      <span className={cn('font-mono', signal.mode === 'LIVE' ? 'text-emerald-400' : 'text-amber-400')}>
                        {signal.mode}
                      </span>
                    </div>
                  )}
                </div>
              </div>

              {/* AI Analysis */}
              <div className="space-y-2">
                <span className="text-[10px] text-zinc-500 uppercase tracking-wider font-medium">
                  AI Analysis
                </span>
                <div className="space-y-1.5 text-[11px]">
                  {ai?.zone_type && (
                    <div className="flex justify-between">
                      <span className="text-zinc-500">Zone</span>
                      <span className="font-mono text-zinc-300">{ai.zone_type.toUpperCase()} {ai.zone_grade || ''}</span>
                    </div>
                  )}
                  {ai?.entry_model && (
                    <div className="flex justify-between">
                      <span className="text-zinc-500">Model</span>
                      <span className="font-mono text-zinc-300">{ai.entry_model}</span>
                    </div>
                  )}
                  {ai?.decision && (
                    <div className="flex justify-between">
                      <span className="text-zinc-500">Decision</span>
                      <span className={cn('font-mono font-semibold', ai.decision === 'GO' ? 'text-emerald-400' : 'text-rose-400')}>
                        {ai.decision}
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
                <span className="text-[10px] text-zinc-500 uppercase tracking-wider font-medium">
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
                      <span className={cn('font-mono font-semibold', pnl >= 0 ? 'text-emerald-400' : 'text-rose-400')}>
                        {pnl >= 0 ? '+' : ''}${pnl.toFixed(2)}
                      </span>
                    </div>
                  )}
                  {signal.pnl_percentage != null && (
                    <div className="flex justify-between">
                      <span className="text-zinc-500">PnL %</span>
                      <span className={cn('font-mono', signal.pnl_percentage >= 0 ? 'text-emerald-400' : 'text-rose-400')}>
                        {signal.pnl_percentage >= 0 ? '+' : ''}{signal.pnl_percentage.toFixed(2)}%
                      </span>
                    </div>
                  )}
                </div>
                <button
                  onClick={(e) => { e.stopPropagation(); onInspect(signal); }}
                  className="mt-3 flex items-center gap-1.5 text-[10px] text-zinc-500 hover:text-zinc-300 transition-colors font-mono"
                >
                  <ExternalLink className="w-3 h-3" />
                  Full Inspector
                </button>
              </div>
            </div>
          </td>
        </tr>
      )}
    </>
  );
}
