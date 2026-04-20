/** @vitest-environment jsdom */

import { act } from 'react';
import { createRoot, Root } from 'react-dom/client';
import { afterEach, beforeEach, describe, expect, it } from 'vitest';
import { SignalTable } from './SignalTable';
import type { TradingSignal } from '@/types/trading';
import { useState } from 'react';

const signals: TradingSignal[] = [
  {
    id: 'sig-1',
    created_at: '2026-04-16T10:00:00.000Z',
    symbol: 'GBPUSD',
    side: 'buy',
    status: 'closed',
    price: 1.25,
    strategy_id: 'liq_sd_v1',
    strategy_version: '1',
    strategy_name: 'Liquidity S&D',
  },
  {
    id: 'sig-2',
    created_at: '2026-04-16T11:00:00.000Z',
    symbol: 'EURUSD',
    side: 'sell',
    status: 'filtered',
    price: 1.08,
    strategy_id: 'breakout_v1',
    strategy_version: '2',
    strategy_name: 'Breakout',
  },
  {
    id: 'sig-3',
    created_at: '2026-04-16T12:00:00.000Z',
    symbol: 'GBPNZD',
    side: 'sell',
    status: 'symbol_blacklisted',
    price: 2.29909,
    strategy_id: 'liq_sd_v1',
    strategy_version: '1',
    strategy_name: 'Liquidity S&D',
  },
];

describe('SignalTable', () => {
  let container: HTMLDivElement;
  let root: Root;

  beforeEach(() => {
    container = document.createElement('div');
    document.body.appendChild(container);
    root = createRoot(container);
  });

  afterEach(() => {
    act(() => root.unmount());
    container.remove();
  });

  it('renders strategy badges and filters rows by strategy', () => {
    function Harness() {
      const [strategyFilter, setStrategyFilter] = useState<string | undefined>();

      return (
        <SignalTable
          signals={signals}
          strategyFilter={strategyFilter}
          onStrategyFilterChange={setStrategyFilter}
          strategyOptions={[
            { value: 'liq_sd_v1', label: 'liq_sd_v1' },
            { value: 'breakout_v1', label: 'breakout_v1' },
          ]}
          strategySignalCounts={{ liq_sd_v1: 1, breakout_v1: 1 }}
        />
      );
    }

    act(() => {
      root.render(<Harness />);
    });

    expect(container.textContent).toContain('liq_sd_v1@1');
    expect(container.textContent).toContain('breakout_v1@2');

    const breakoutButton = Array.from(container.querySelectorAll('button')).find(
      (button) => button.textContent?.includes('breakout_v1')
    );

    expect(breakoutButton).not.toBeUndefined();

    act(() => {
      breakoutButton?.dispatchEvent(new MouseEvent('click', { bubbles: true }));
    });

    expect(container.textContent).toContain('EURUSD');
    expect(container.textContent).not.toContain('GBPUSD');
  });

  it('shows symbol_blacklisted rows under the filtered tab', () => {
    act(() => {
      root.render(<SignalTable signals={signals} />);
    });

    const filteredButton = Array.from(container.querySelectorAll('button')).find(
      (button) => button.textContent?.includes('Filtered')
    );

    expect(filteredButton?.textContent).toContain('2');

    act(() => {
      filteredButton?.dispatchEvent(new MouseEvent('click', { bubbles: true }));
    });

    expect(container.textContent).toContain('EURUSD');
    expect(container.textContent).toContain('GBPNZD');
    expect(container.textContent).toContain('FILTERED');
    expect(container.textContent).not.toContain('GBPUSD');
  });
});
