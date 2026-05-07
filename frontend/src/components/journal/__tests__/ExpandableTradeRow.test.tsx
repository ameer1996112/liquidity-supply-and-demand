/** @vitest-environment jsdom */

import { createRoot } from 'react-dom/client';
import { act } from 'react';
import { describe, expect, test, vi } from 'vitest';
import { ExpandableTradeRow } from '../ExpandableTradeRow';
import { TradingSignal } from '@/types/trading';

vi.mock('../TradeNoteEditor', () => ({
  TradeNoteEditor: () => null,
  TradeNoteIndicator: () => null,
}));

describe('ExpandableTradeRow', () => {
  test('renders technical setup values as prices, not PnL currency', () => {
    const container = document.createElement('div');
    const root = createRoot(container);
    const signal = {
      id: 'trade-1',
      created_at: '2026-05-07T07:50:00Z',
      symbol: 'XAUUSD',
      side: 'sell',
      status: 'closed',
      entry: 4739.14,
      sl: 4745.11,
      tp: 4643.62,
      rr_ratio: 16,
      setup_evidence: null,
      zone_type: 'supply',
      zone_grade: 'B+',
      entry_model: 'flip',
    } as TradingSignal;

    act(() => {
      root.render(
        <table>
          <tbody>
            <ExpandableTradeRow signal={signal} onInspect={() => undefined} />
          </tbody>
        </table>,
      );
    });

    act(() => {
      container.querySelector('tr')?.dispatchEvent(new MouseEvent('click', { bubbles: true }));
    });

    expect(container.textContent).toContain('4739.14');
    expect(container.textContent).toContain('4745.11');
    expect(container.textContent).toContain('4643.62');
    expect(container.textContent).not.toContain('+$4739.14');
    expect(container.textContent).not.toContain('$4739.14');
    expect(container.textContent).not.toContain('-- lots');
    root.unmount();
  });

  test('uses native size as a fallback for position size', () => {
    const container = document.createElement('div');
    const root = createRoot(container);
    const signal = {
      id: 'trade-2',
      created_at: '2026-05-07T12:00:00Z',
      symbol: 'USDJPY',
      side: 'sell',
      status: 'open',
      entry: 156.404,
      sl: 156.503,
      tp: 156.156,
      size: 0.4,
      setup_evidence: null,
    } as TradingSignal;

    act(() => {
      root.render(
        <table>
          <tbody>
            <ExpandableTradeRow signal={signal} onInspect={() => undefined} />
          </tbody>
        </table>,
      );
    });

    act(() => {
      container.querySelector('tr')?.dispatchEvent(new MouseEvent('click', { bubbles: true }));
    });

    expect(container.textContent).toContain('0.4 lots');
    expect(container.textContent).not.toContain('-- lots');
    root.unmount();
  });
});
