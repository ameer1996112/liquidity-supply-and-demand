'use client';

import { TradingSignal, getSymbol, getSide, getPnl } from '@/types/trading';
import { Badge } from '@/components/ui/badge';
import { cn } from '@/lib/utils';
import { formatDistanceToNowStrict } from 'date-fns';
import { TrendingUp, TrendingDown } from 'lucide-react';

interface ActiveTradeRowProps {
  signal: TradingSignal;
  onClick: () => void;
}

export function ActiveTradeRow({ signal, onClick }: ActiveTradeRowProps) {
  const symbol = getSymbol(signal);
  const side = getSide(signal);
  const pnl = getPnl(signal);
  const isBuy = side === 'buy';

  const entry = signal.price ?? signal.entry;
  const rr = signal.rr_ratio;
  const timeHeld = formatDistanceToNowStrict(new Date(signal.created_at), { addSuffix: false });

  return (
    <button
      onClick={onClick}
      className={cn(
        'w-full flex items-center gap-3 px-3 py-2.5 rounded-md',
        'border-l-2 border-l-[#2962ff] bg-[#1e222d]/50',
        'hover:bg-[#2a2e39]/60 transition-colors cursor-pointer text-left'
      )}
    >
      {/* Symbol + Side */}
      <div className="flex items-center gap-2 min-w-[110px]">
        <span className="font-mono text-sm font-bold text-zinc-100">{symbol}</span>
        <Badge
          className={cn(
            'font-mono text-[9px] font-bold border-0 px-1.5 py-0 gap-0.5',
            isBuy
              ? 'bg-[#26a69a]/20 text-[#26a69a]'
              : 'bg-[#ef5350]/20 text-[#ef5350]'
          )}
        >
          {isBuy ? <TrendingUp className="w-2.5 h-2.5" /> : <TrendingDown className="w-2.5 h-2.5" />}
          {side.toUpperCase()}
        </Badge>
      </div>

      {/* Entry Price */}
      <div className="flex flex-col min-w-[70px]">
        <span className="text-[9px] text-zinc-600 uppercase">Entry</span>
        <span className="font-mono text-xs text-zinc-300 tabular-nums">
          {entry != null ? Number(entry).toFixed(symbol.includes('JPY') ? 3 : 5) : '--'}
        </span>
      </div>

      {/* R:R */}
      <div className="flex flex-col min-w-[40px]">
        <span className="text-[9px] text-zinc-600 uppercase">R:R</span>
        <span className="font-mono text-xs text-zinc-400 tabular-nums">
          {rr ? `1:${rr.toFixed(1)}` : '--'}
        </span>
      </div>

      {/* Time Held */}
      <div className="flex-1 text-right">
        <span className="font-mono text-[10px] text-zinc-600">{timeHeld}</span>
      </div>

      {/* PnL */}
      <div className="min-w-[60px] text-right">
        {pnl != null ? (
          <span
            className={cn(
              'font-mono text-xs font-bold tabular-nums',
              pnl >= 0 ? 'text-[#26a69a]' : 'text-[#ef5350]'
            )}
          >
            {pnl >= 0 ? '+' : ''}{pnl.toFixed(2)}
          </span>
        ) : (
          <span className="font-mono text-xs text-zinc-600">--</span>
        )}
      </div>
    </button>
  );
}
