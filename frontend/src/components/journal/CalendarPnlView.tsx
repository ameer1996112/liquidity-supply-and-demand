'use client';

import { useMemo, useState } from 'react';
import { cn } from '@/lib/utils';
import {
  format,
  startOfMonth,
  endOfMonth,
  eachDayOfInterval,
  getDay,
  addMonths,
  subMonths,
} from 'date-fns';
import { ChevronLeft, ChevronRight } from 'lucide-react';
import type { TradingSignal } from '@/types/trading';
import { getPnl } from '@/types/trading';

interface CalendarPnlViewProps {
  signals: TradingSignal[];
}

interface DayData {
  date: Date;
  pnl: number;
  tradeCount: number;
  wins: number;
  losses: number;
}

function buildDayMap(signals: TradingSignal[]): Map<string, DayData> {
  const map = new Map<string, DayData>();

  for (const signal of signals) {
    const pnl = getPnl(signal);
    if (pnl == null) continue;

    // Skip zero-PnL trades (stale positions from cleanup script)
    if (pnl === 0) continue;

    // Use closed_at for accurate daily grouping (when trade finished, not when signal created)
    const s = signal as TradingSignal & { closed_at?: string };
    const dateTimestamp = s.closed_at || signal.created_at;
    const dateStr = format(new Date(dateTimestamp), 'yyyy-MM-dd');
    const existing = map.get(dateStr);

    if (existing) {
      existing.pnl += pnl;
      existing.tradeCount += 1;
      if (pnl > 0) existing.wins += 1;
      else if (pnl < 0) existing.losses += 1;
    } else {
      map.set(dateStr, {
        date: new Date(dateTimestamp),
        pnl,
        tradeCount: 1,
        wins: pnl > 0 ? 1 : 0,
        losses: pnl < 0 ? 1 : 0,
      });
    }
  }

  return map;
}

function formatPnl(pnl: number): string {
  const abs = Math.abs(pnl);
  if (abs >= 1000) return `${pnl >= 0 ? '+' : '-'}$${(abs / 1000).toFixed(1)}K`;
  return `${pnl >= 0 ? '+' : '-'}$${abs.toFixed(0)}`;
}

const WEEKDAYS = ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat'];

export function CalendarPnlView({ signals }: CalendarPnlViewProps) {
  const [currentMonth, setCurrentMonth] = useState(() => new Date());
  const [hoveredDay, setHoveredDay] = useState<string | null>(null);

  const dayMap = useMemo(() => buildDayMap(signals), [signals]);

  const days = useMemo(() => {
    const start = startOfMonth(currentMonth);
    const end = endOfMonth(currentMonth);
    return eachDayOfInterval({ start, end });
  }, [currentMonth]);

  const startPadding = getDay(startOfMonth(currentMonth));

  const monthlySummary = useMemo(() => {
    let totalPnl = 0;
    let tradingDays = 0;
    let winDays = 0;
    let lossDays = 0;
    let totalTrades = 0;

    days.forEach((day) => {
      const key = format(day, 'yyyy-MM-dd');
      const data = dayMap.get(key);
      if (data) {
        totalPnl += data.pnl;
        tradingDays += 1;
        totalTrades += data.tradeCount;
        if (data.pnl > 0) winDays += 1;
        else if (data.pnl < 0) lossDays += 1;
      }
    });

    return { totalPnl, tradingDays, winDays, lossDays, totalTrades };
  }, [days, dayMap]);

  return (
    <div className='space-y-4'>
      {/* Header */}
      <div className='flex items-center justify-between'>
        <div className='flex items-center gap-3'>
          <button
            onClick={() => setCurrentMonth((m) => subMonths(m, 1))}
            className='flex h-8 w-8 items-center justify-center rounded-lg border border-[var(--to-border)] text-[var(--to-text-dim)] hover:text-[var(--to-text-primary)] hover:bg-[var(--to-surface-raised)] transition-colors'
          >
            <ChevronLeft className='h-4 w-4' />
          </button>
          <span
            className='text-[15px] font-bold text-[var(--to-text-primary)]'
            style={{ fontFamily: 'var(--font-sans)' }}
          >
            {format(currentMonth, 'MMMM yyyy')}
          </span>
          <button
            onClick={() => setCurrentMonth((m) => addMonths(m, 1))}
            className='flex h-8 w-8 items-center justify-center rounded-lg border border-[var(--to-border)] text-[var(--to-text-dim)] hover:text-[var(--to-text-primary)] hover:bg-[var(--to-surface-raised)] transition-colors'
          >
            <ChevronRight className='h-4 w-4' />
          </button>
        </div>

        {/* Monthly stats */}
        <div className='flex items-center gap-6'>
          <div className='text-right'>
            <p className='text-[11px] text-[var(--to-text-dim)] font-mono uppercase tracking-wider'>
              Monthly P&L
            </p>
            <p
              className={cn(
                'text-[18px] font-bold tabular-nums',
                monthlySummary.totalPnl >= 0
                  ? 'text-[#0ecb81]'
                  : 'text-[#f6465d]'
              )}
              style={{ fontFamily: 'var(--font-mono)' }}
            >
              {monthlySummary.totalPnl >= 0 ? '+' : ''}$
              {monthlySummary.totalPnl.toFixed(2)}
            </p>
          </div>
          <div className='text-right'>
            <p className='text-[11px] text-[var(--to-text-dim)] font-mono uppercase tracking-wider'>
              Win Days
            </p>
            <p
              className='text-[18px] font-bold text-[#0ecb81]'
              style={{ fontFamily: 'var(--font-mono)' }}
            >
              {monthlySummary.winDays}
              <span className='text-[12px] text-[var(--to-text-dim)] ml-1'>
                / {monthlySummary.tradingDays}
              </span>
            </p>
          </div>
          <div className='text-right'>
            <p className='text-[11px] text-[var(--to-text-dim)] font-mono uppercase tracking-wider'>
              Trades
            </p>
            <p
              className='text-[18px] font-bold text-[var(--to-text-primary)]'
              style={{ fontFamily: 'var(--font-mono)' }}
            >
              {monthlySummary.totalTrades}
            </p>
          </div>
        </div>
      </div>

      {/* Weekday headers */}
      <div className='grid grid-cols-7 gap-1.5'>
        {WEEKDAYS.map((d) => (
          <div
            key={d}
            className='text-center text-[11px] font-bold uppercase tracking-widest text-[var(--to-text-dim)] py-2'
            style={{ fontFamily: 'var(--font-mono)' }}
          >
            {d}
          </div>
        ))}
      </div>

      {/* Calendar grid */}
      <div className='grid grid-cols-7 gap-1.5'>
        {/* Padding cells */}
        {Array.from({ length: startPadding }).map((_, i) => (
          <div
            key={`pad-${i}`}
            className='rounded-xl border border-[var(--to-border)]/30 aspect-square min-h-[80px]'
          />
        ))}

        {/* Day cells */}
        {days.map((day) => {
          const key = format(day, 'yyyy-MM-dd');
          const data = dayMap.get(key);
          const isHovered = hoveredDay === key;
          const winRate =
            data && data.wins + data.losses > 0
              ? ((data.wins / (data.wins + data.losses)) * 100).toFixed(1)
              : null;

          const isProfit = data && data.pnl > 0;
          const isLoss = data && data.pnl < 0;

          return (
            <div
              key={key}
              className={cn(
                'relative flex flex-col rounded-xl border transition-all cursor-default min-h-[80px] p-2',
                data
                  ? isProfit
                    ? 'border-[#0ecb81]/30 bg-[#0ecb81]/8 hover:border-[#0ecb81]/50 hover:bg-[#0ecb81]/12'
                    : 'border-[#f6465d]/30 bg-[#f6465d]/8 hover:border-[#f6465d]/50 hover:bg-[#f6465d]/12'
                  : 'border-[var(--to-border)]/40 bg-[var(--to-surface)]/50',
                isHovered && 'scale-[1.02] z-10 shadow-lg'
              )}
              onMouseEnter={() => setHoveredDay(key)}
              onMouseLeave={() => setHoveredDay(null)}
            >
              {/* Day number */}
              <span
                className={cn(
                  'text-[11px] font-semibold self-end',
                  data
                    ? isProfit
                      ? 'text-[#0ecb81]'
                      : 'text-[#f6465d]'
                    : 'text-[var(--to-text-dim)]'
                )}
                style={{ fontFamily: 'var(--font-mono)' }}
              >
                {format(day, 'd')}
              </span>

              {/* Data */}
              {data && (
                <div className='flex flex-col gap-0.5 mt-auto'>
                  <span
                    className={cn(
                      'text-[12px] font-bold tabular-nums leading-tight',
                      isProfit ? 'text-[#0ecb81]' : 'text-[#f6465d]'
                    )}
                    style={{ fontFamily: 'var(--font-mono)' }}
                  >
                    {formatPnl(data.pnl)}
                  </span>
                  <span
                    className='text-[10px] text-[var(--to-text-dim)] tabular-nums'
                    style={{ fontFamily: 'var(--font-mono)' }}
                  >
                    {data.tradeCount}{' '}
                    {data.tradeCount === 1 ? 'trade' : 'trades'}
                  </span>
                  {winRate !== null && (
                    <span
                      className={cn(
                        'text-[10px] font-semibold tabular-nums',
                        isProfit ? 'text-[#0ecb81]/80' : 'text-[#f6465d]/80'
                      )}
                      style={{ fontFamily: 'var(--font-mono)' }}
                    >
                      {winRate}%
                    </span>
                  )}
                </div>
              )}

              {/* Hover tooltip */}
              {isHovered && data && (
                <div
                  className='absolute bottom-full left-1/2 -translate-x-1/2 mb-2 z-30 w-40 rounded-xl border border-[var(--to-border)] bg-[#0d1117]/98 px-3 py-2.5 text-[11px] shadow-2xl backdrop-blur-sm pointer-events-none'
                  style={{ fontFamily: 'var(--font-mono)' }}
                >
                  <p className='font-bold text-[var(--to-text-primary)] mb-2 text-[12px]'>
                    {format(day, 'MMM d, yyyy')}
                  </p>
                  <div className='space-y-1'>
                    <div className='flex justify-between'>
                      <span className='text-[var(--to-text-dim)]'>P&L</span>
                      <span
                        className={
                          isProfit ? 'text-[#0ecb81]' : 'text-[#f6465d]'
                        }
                      >
                        {data.pnl >= 0 ? '+' : ''}${data.pnl.toFixed(2)}
                      </span>
                    </div>
                    <div className='flex justify-between'>
                      <span className='text-[var(--to-text-dim)]'>Trades</span>
                      <span className='text-[var(--to-text-secondary)]'>
                        {data.tradeCount}
                      </span>
                    </div>
                    <div className='flex justify-between'>
                      <span className='text-[var(--to-text-dim)]'>
                        Win Rate
                      </span>
                      <span
                        className={
                          isProfit ? 'text-[#0ecb81]' : 'text-[#f6465d]'
                        }
                      >
                        {winRate}%
                      </span>
                    </div>
                    <div className='flex justify-between'>
                      <span className='text-[var(--to-text-dim)]'>W / L</span>
                      <span className='text-[var(--to-text-secondary)]'>
                        {data.wins} / {data.losses}
                      </span>
                    </div>
                  </div>
                </div>
              )}
            </div>
          );
        })}
      </div>

      {/* Legend */}
      <div className='flex items-center justify-end gap-5 pt-3 border-t border-[var(--to-border)]'>
        <div className='flex items-center gap-2'>
          <div className='h-3 w-3 rounded-sm bg-[#0ecb81]/40 border border-[#0ecb81]/30' />
          <span className='text-[10px] text-[var(--to-text-dim)] font-mono uppercase tracking-wider'>
            Profit Day
          </span>
        </div>
        <div className='flex items-center gap-2'>
          <div className='h-3 w-3 rounded-sm bg-[#f6465d]/40 border border-[#f6465d]/30' />
          <span className='text-[10px] text-[var(--to-text-dim)] font-mono uppercase tracking-wider'>
            Loss Day
          </span>
        </div>
      </div>
    </div>
  );
}
