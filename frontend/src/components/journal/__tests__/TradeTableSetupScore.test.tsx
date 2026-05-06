/** @vitest-environment jsdom */

import { createRoot } from 'react-dom/client';
import { act } from 'react';
import { describe, expect, test, vi } from 'vitest';
import { TradeTable } from '../TradeTable';
import type { TradingSignal } from '@/types/trading';

vi.mock('../TradeNoteEditor', () => ({
  TradeNoteEditor: () => <div />,
  TradeNoteIndicator: () => <span />,
}));

describe('TradeTable setup scoring', () => {
  test('shows setup grade and score in journal rows', () => {
    const container = document.createElement('div');
    const root = createRoot(container);
    const signal: TradingSignal = {
      id: 'sig-setup-score',
      created_at: '2026-05-06T09:00:00.000Z',
      symbol: 'GBPJPY',
      side: 'buy',
      status: 'closed',
      entry: 193.45,
      sl: 193.38,
      tp: 193.66,
      setup_score: 88.4,
      setup_grade: 'A+',
      setup_strengths: ['liquidity_sweep', 'multi_candle_liquidity'],
      setup_weaknesses: ['flip_entry_model'],
    };

    act(() => {
      root.render(<TradeTable signals={[signal]} onInspect={() => {}} />);
    });

    expect(container.textContent).toContain('A+');
    expect(container.textContent).toContain('88');
    root.unmount();
  });
});
