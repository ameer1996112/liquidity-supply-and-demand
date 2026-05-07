import { describe, expect, test } from 'vitest';
import { normalizeSignal } from '../trading';

describe('normalizeSignal', () => {
  test('preserves DB size and exposes it as position size for journal rows', () => {
    const signal = normalizeSignal({
      id: 'trade-1',
      created_at: '2026-05-07T12:00:00Z',
      symbol: 'USDJPY',
      side: 'sell',
      status: 'OPEN',
      entry: 156.404,
      sl: 156.503,
      tp: 156.156,
      size: 0.4,
    });

    expect(signal.size).toBe(0.4);
    expect(signal.position_size).toBe(0.4);
  });
});
