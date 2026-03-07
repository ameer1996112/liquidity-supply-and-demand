'use client';

import { useMemo, useState } from 'react';
import { cn } from '@/lib/utils';
import {
  format,
  startOfMonth,
  endOfMonth,
  eachDayOfInterval,
  getDay,
  isSameMonth,
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

    const dateStr = format(new Date(signal.created_at), 'yyyy-MM-dd');
    const existing = map.get(dateStr);

    if (existing) {
      existing.pnl += pnl;
      existing.tradeCount += 1;
      if (pnl > 0) existing.wins += 1;
      else if (pnl < 0) existing.losses += 1;
    } else {
      map.set(dateStr, {
        date: new Date(signal.created_at),
        pnl,
        tradeCount: 1,
        wins: pnl > 0 ? 1 : 0,
        losses: pnl < 0 ? 1 : 0,
      });
    }
  }

  return map;
}

function getDayColor(pnl: number, maxAbsPnl: number): string {
  if (pnl === 0) return 'transparent';
  const intensity = Math.min(Math.abs(pnl) / (maxAbsPnl || 1), 1);
  if (pnl > 0) {
    const alpha = 0.15 + intensity * 0.55;
    return `rgba(14, 203, 129, ${alpha})`;
  } else {
    const alpha = 0.15 + intensity * 0.55;
    return `rgba(246, 70, 93, ${alpha})`;
  }
}

const WEEKDAYS = ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat'];

export function CalendarPnlView({ signals }: CalendarPnlViewProps) {
  const [currentMonth, setCurrentMonth] = useState(() => new Date());
  const [hoveredDay, setHoveredDay] = useState<string | null>(null);

  const dayMap = useMemo(() => buildDayMap(signals), [signals]);

  const maxAbsPnl = useMemo(() => {
    let max = 0;
    dayMap.forEach((d) => {
      if (Math.abs(d.pnl) > max) max = Math.abs(d.pnl);
    });
    return max;
  }, [dayMap]);

  const days = useMemo(() => {
    const start = startOfMonth(currentMonth);
    const end = endOfMonth(currentMonth);
    return eachDayOfInterval({ start, end });
  }, [currentMonth]);

  const startPadding = getDay(startOfMonth(currentMonth));

  // Monthly summary
  const monthlySummary = useMemo(() => {
    let totalPnl = 0;
    let tradingDays = 0;
    let winDays = 0;
    let lossDays = 0;

    days.forEach((day) => {
      const key = format(day, 'yyyy-MM-dd');
      const data = dayMap.get(key);
      if (data) {
        totalPnl += data.pnl;
        tradingDays += 1;
        if (data.pnl > 0) winDays += 1;
        else if (data.pnl < 0) lossDays += 1;
      }
    });

    return { totalPnl, tradingDays, winDays, lossDays };
  }, [days, dayMap]);

  const hoveredData = hoveredDay ? dayMap.get(hoveredDay) : null;

  return (
    <div className='tv-card p-4 space-y-4'>
      {/* Header */}
      <div className='flex items-center justify-between'>
        <div className='flex items-center gap-3'>
          <button
            onClick={() => setCurrentMonth((m) => subMonths(m, 1))}
            className='flex h-7 w-7 items-center justify-center rounded-lg border border-[var(--to-border)] text-[var(--to-text-dim)] hover:text-[var(--to-text-primary)] hover:bg-[var(--to-surface-raised)] transition-colors'
          >
            <ChevronLeft className='h-3.5 w-3.5' />
          </button>
          <span
            className='text-[13px] font-semibold text-[var(--to-text-primary)]'
            style={{ fontFamily: 'var(--font-sans)' }}
          >
            {format(currentMonth, 'MMMM yyyy')}
          </span>
          <button
            onClick={() => setCurrentMonth((m) => addMonths(m, 1))}
            className='flex h-7 w-7 items-center justify-center rounded-lg border border-[var(--to-border)] text-[var(--to-text-dim)] hover:text-[var(--to-text-primary)] hover:bg-[var(--to-surface-raised)] transition-colors'
          >
            <ChevronRight className='h-3.5 w-3.5' />
          </button>
        </div>

        {/* Monthly summary */}
        <div className='flex items-center gap-4'>
          <div className='text-right'>
            <p
              className={cn(
                'text-[13px] font-bold tabular-nums',
                monthlySummary.totalPnl >= 0
                  ? 'text-[#0ecb81]'
                  : 'text-[#f6465d]'
              )}
              style={{ fontFamily: 'var(--font-mono)' }}
            >
              {monthlySummary.totalPnl >= 0 ? '+' : ''}$
              {monthlySummary.totalPnl.toFixed(2)}
            </p>
            <p
              className='text-[9px] text-[var(--to-text-dim)]'
              style={{ fontFamily: 'var(--font-mono)' }}
            >
              {monthlySummary.winDays}W / {monthlySummary.lossDays}L ·{' '}
              {monthlySummary.tradingDays} days
            </p>
          </div>
        </div>
      </div>

      {/* Weekday headers */}
      <div className='grid grid-cols-7 gap-1'>
        {WEEKDAYS.map((d) => (
          <div
            key={d}
            className='text-center text-[9px] font-semibold uppercase tracking-wider text-[var(--to-text-dim)] py-1'
            style={{ fontFamily: 'var(--font-mono)' }}
          >
            {d}
          </div>
        ))}
      </div>

      {/* Calendar grid */}
      <div className='grid grid-cols-7 gap-1'>
        {/* Padding cells */}
        {Array.from({ length: startPadding }).map((_, i) => (
          <div key={`pad-${i}`} />
        ))}

        {/* Day cells */}
        {days.map((day) => {
          const key = format(day, 'yyyy-MM-dd');
          const data = dayMap.get(key);
          const isHovered = hoveredDay === key;
          const bgColor = data
            ? getDayColor(data.pnl, maxAbsPnl)
            : 'transparent';

          return (
            <div
              key={key}
              className={cn(
                'relative flex flex-col items-center justify-center rounded-lg border transition-all cursor-default',
                'aspect-square min-h-[36px]',
                data
                  ? 'border-[var(--to-border)]/60 hover:border-[var(--to-border)] hover:scale-105'
                  : 'border-transparent',
                isHovered && 'scale-105 z-10'
              )}
              style={{ backgroundColor: bgColor }}
              onMouseEnter={() => setHoveredDay(key)}
              onMouseLeave={() => setHoveredDay(null)}
            >
              <span
                className={cn(
                  'text-[10px] font-medium',
                  data
                    ? data.pnl >= 0
                      ? 'text-[#0ecb81]'
                      : 'text-[#f6465d]'
                    : 'text-[var(--to-text-dim)]'
                )}
                style={{ fontFamily: 'var(--font-mono)' }}
              >
                {format(day, 'd')}
              </span>
              {data && (
                <span
                  className={cn(
                    'text-[8px] tabular-nums font-semibold',
                    data.pnl >= 0 ? 'text-[#0ecb81]' : 'text-[#f6465d]'
                  )}
                  style={{ fontFamily: 'var(--font-mono)' }}
                >
                  {data.pnl >= 0 ? '+' : ''}${Math.abs(data.pnl).toFixed(0)}
                </span>
              )}

              {/* Tooltip */}
              {isHovered && data && (
                <div
                  className='absolute bottom-full left-1/2 -translate-x-1/2 mb-2 z-20 w-36 rounded-lg border border-[var(--to-border)] bg-[#0d1117]/95 px-2.5 py-2 text-[10px] shadow-xl backdrop-blur-sm pointer-events-none'
                  style={{ fontFamily: 'var(--font-mono)' }}
                >
                  <p className='font-semibold text-[var(--to-text-primary)] mb-1'>
                    {format(day, 'MMM d, yyyy')}
                  </p>
                  <div className='space-y-0.5'>
                    <div className='flex justify-between'>
                      <span className='text-[var(--to-text-dim)]'>P&L</span>
                      <span
                        className={
                          data.pnl >= 0 ? 'text-[#0ecb81]' : 'text-[#f6465d]'
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
                      <span className='text-[var(--to-text-dim)]'>W/L</span>
                      <span className='text-[var(--to-text-secondary)]'>
                        {data.wins}/{data.losses}
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
      <div className='flex items-center justify-end gap-4 pt-1 border-t border-[var(--to-border)]'>
        <div className='flex items-center gap-1.5'>
          <div
            className='h-2.5 w-2.5 rounded-sm'
            style={{ backgroundColor: 'rgba(14,203,129,0.5)' }}
          />
          <span
            className='text-[9px] text-[var(--to-text-dim)]'
            style={{ fontFamily: 'var(--font-mono)' }}
          >
            Profit day
          </span>
        </div>
        <div className='flex items-center gap-1.5'>
          <div
            className='h-2.5 w-2.5 rounded-sm'
            style={{ backgroundColor: 'rgba(246,70,93,0.5)' }}
          />
          <span
            className='text-[9px] text-[var(--to-text-dim)]'
            style={{ fontFamily: 'var(--font-mono)' }}
          >
            Loss day
          </span>
        </div>
      </div>
    </div>
  );
}
