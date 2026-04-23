import { describe, expect, it } from 'vitest';
import { buildOpenPositionFallback } from './openPositionFallback';
import type { TradingSignal } from '@/types/trading';

describe('buildOpenPositionFallback', () => {
  it('uses signal.size when position_size is missing', () => {
    const signals = [
      {
        id: 'sig-1',
        created_at: '2026-04-23T10:00:00.000Z',
        symbol: 'GBPUSD',
        side: 'sell',
        status: 'open',
        size: 0.81,
      },
    ] as TradingSignal[];

    const [position] = buildOpenPositionFallback(signals, Date.parse('2026-04-23T11:00:00.000Z'));

    expect(position?.size).toBe(0.81);
    expect(position?.hold_duration_seconds).toBe(3600);
  });
});
