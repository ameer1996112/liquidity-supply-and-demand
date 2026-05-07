/** @vitest-environment jsdom */

import { act } from 'react';
import { createRoot, Root } from 'react-dom/client';
import { afterEach, beforeEach, describe, expect, it } from 'vitest';
import { SignalTable } from './SignalTable';
import type { TradingSignal } from '@/types/trading';
import type { ActivePosition } from '@/hooks/usePositions';
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
    setup_score: 88.4,
    setup_grade: 'A+',
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
    expect(container.textContent).toContain('Setup Q');
    expect(container.textContent).toContain('A+');
    expect(container.textContent).toContain('88');
    expect(container.textContent).toContain('AI Conv.');
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

  it('shows pending council placeholders as processing, not skipped', () => {
    act(() => {
      root.render(
        <SignalTable
          signals={[{ ...signals[0], status: 'OPEN' }]}
          councilMap={{
            'sig-1': {
              recommendation: 'pending',
              confidence: 0,
              votes: {},
              status: 'pending',
            },
          }}
        />
      );
    });

    expect(container.textContent?.toLowerCase()).toContain('processing');
    expect(container.textContent?.toLowerCase()).not.toContain('skip');
  });

  it('does not show stale pending council placeholders for closed signals', () => {
    act(() => {
      root.render(
        <SignalTable
          signals={[signals[0]]}
          councilMap={{
            'sig-1': {
              recommendation: 'pending',
              confidence: 0,
              votes: {},
              status: 'pending',
            },
          }}
        />
      );
    });

    expect(container.textContent?.toLowerCase()).not.toContain('processing');
    expect(container.textContent).toContain('CLOSED');
  });

  it('uses realized DB PnL instead of live broker PnL for closed signals', () => {
    const closedSignal: TradingSignal = {
      ...signals[0],
      id: '515',
      symbol: 'XAUUSD',
      pnl: 419.84,
      pnl_usd: 419.84,
      commission: -0.8,
      swap: 0,
      status: 'closed',
    };
    const brokerMap: Record<string, ActivePosition> = {
      '515': {
        id: 515,
        symbol: 'XAUUSD',
        side: 'sell',
        entry: 4604.85,
        sl: 4613.37,
        tp: 4468.53,
        size: 0.08,
        broker_order_id: '89146771',
        current_price: 4464.25,
        live_pnl: 1126.76,
        live_pnl_pct: 2.25,
        hold_duration_seconds: 3600,
        created_at: closedSignal.created_at,
        zone_type: null,
        entry_model: null,
        rr_ratio: null,
        is_stale: false,
        broker_exists: false,
      },
    };

    act(() => {
      root.render(<SignalTable signals={[closedSignal]} brokerMap={brokerMap} />);
    });

    expect(container.textContent).toContain('420.64');
    expect(container.textContent).not.toContain('1126.76');
  });

  it('uses realized DB PnL when a broker-synced signal has close data but stale open status', () => {
    const closedSignal: TradingSignal = {
      ...signals[0],
      id: '516',
      symbol: 'XAUUSD',
      pnl: 419.84,
      pnl_usd: 419.84,
      commission: -0.8,
      swap: 0,
      status: 'executed',
      closed_at: '2026-04-16T13:00:00.000Z',
      exit_price: 4468.53,
    };
    const brokerMap: Record<string, ActivePosition> = {
      '516': {
        id: 516,
        symbol: 'XAUUSD',
        side: 'sell',
        entry: 4604.85,
        sl: 4613.37,
        tp: 4468.53,
        size: 0.08,
        broker_order_id: '89146771',
        current_price: 4464.25,
        live_pnl: 1126.76,
        live_pnl_pct: 2.25,
        hold_duration_seconds: 3600,
        created_at: closedSignal.created_at,
        zone_type: null,
        entry_model: null,
        rr_ratio: null,
        is_stale: false,
        broker_exists: false,
      },
    };

    act(() => {
      root.render(<SignalTable signals={[closedSignal]} brokerMap={brokerMap} />);
    });

    expect(container.textContent).toContain('420.64');
    expect(container.textContent).not.toContain('1126.76');
  });

  it('shows spread-aware risk in latest signals', () => {
    const signal: TradingSignal = {
      ...signals[0],
      id: 'risk-sig',
      symbol: 'USDJPY',
      entry: 156.404,
      sl: 156.503,
      size: 0.4,
      risk_usd: 30.44,
      spread_pips: 1.2,
      effective_sl_pips: 11.9,
      pip_value_per_lot: 6.3937,
      status: 'open',
    };

    act(() => {
      root.render(<SignalTable signals={[signal]} />);
    });

    expect(container.textContent).toContain('At Risk');
    expect(container.textContent).toContain('$30.44');
  });
});
