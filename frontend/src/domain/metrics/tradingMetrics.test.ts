import { describe, expect, it } from 'vitest';
import {
  computeTradeKpis,
  formatWinRate,
  isSignalClosed,
  isSignalOpen,
  toPercentFromRatioOrPercent,
} from './tradingMetrics';
import type { TradingSignal } from '@/types/trading';

function mkSignal(partial: Partial<TradingSignal>): TradingSignal {
  return {
    id: partial.id ?? 's1',
    created_at: partial.created_at ?? '2026-01-01T10:00:00.000Z',
    symbol: partial.symbol ?? 'XAUUSD',
    side: partial.side ?? 'buy',
    status: partial.status ?? 'active',
    ...partial,
  };
}

describe('tradingMetrics', () => {
  it('classifies executed with no exit/pnl as open', () => {
    const signal = mkSignal({ status: 'executed', broker_position_id: 'pos-123' });
    expect(isSignalOpen(signal)).toBe(true);
    expect(isSignalClosed(signal)).toBe(false);
  });

  it('classifies executed with closed_at as closed', () => {
    const signal = mkSignal({
      status: 'executed',
      closed_at: '2026-01-01T11:00:00.000Z',
    });
    expect(isSignalClosed(signal)).toBe(true);
    expect(isSignalOpen(signal)).toBe(false);
  });

  it('computes consistent kpis and handles empty trades winrate as null', () => {
    const open = mkSignal({ id: 'a', status: 'active' });
    const win = mkSignal({ id: 'b', status: 'closed', pnl: 100 });
    const loss = mkSignal({ id: 'c', status: 'closed', pnl: -40 });
    const flat = mkSignal({ id: 'd', status: 'closed', pnl: 0 });

    const kpis = computeTradeKpis([open, win, loss, flat]);
    expect(kpis.totalTrades).toBe(3);
    expect(kpis.wins).toBe(1);
    expect(kpis.losses).toBe(1);
    expect(kpis.breakeven).toBe(1);
    expect(kpis.totalPnl).toBe(60);
    expect(kpis.winRatePct).toBeCloseTo(33.333, 2);

    const empty = computeTradeKpis([open]);
    expect(empty.totalTrades).toBe(0);
    expect(empty.winRatePct).toBeNull();
  });

  it('formats winrate with dash/zero behavior when trades=0', () => {
    expect(formatWinRate(null, 0, 'dash')).toBe('—');
    expect(formatWinRate(null, 0, 'zero')).toBe('0.0%');
    expect(formatWinRate(50, 2, 'dash')).toBe('50.0%');
  });

  it('normalizes ratio or percent winrate payloads', () => {
    expect(toPercentFromRatioOrPercent(0.625)).toBeCloseTo(62.5, 5);
    expect(toPercentFromRatioOrPercent(62.5)).toBe(62.5);
    expect(toPercentFromRatioOrPercent(undefined)).toBe(0);
  });
});
