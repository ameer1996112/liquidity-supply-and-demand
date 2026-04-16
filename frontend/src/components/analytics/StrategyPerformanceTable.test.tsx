/** @vitest-environment jsdom */

import { act } from 'react';
import { createRoot, Root } from 'react-dom/client';
import { afterEach, beforeEach, describe, expect, it } from 'vitest';
import { StrategyPerformanceTable } from './StrategyPerformanceTable';

describe('StrategyPerformanceTable', () => {
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

  it('renders strategy rows with version, win rate, and pnl', () => {
    act(() => {
      root.render(
        <StrategyPerformanceTable
          data={[
            {
              strategyId: 'liq_sd_v1',
              strategyVersion: '1',
              label: 'liq_sd_v1@1',
              pnl: 120.5,
              count: 5,
              wins: 3,
              losses: 2,
              winRate: 60,
              avgPnl: 24.1,
            },
            {
              strategyId: 'breakout_v1',
              strategyVersion: '2',
              label: 'breakout_v1@2',
              pnl: -42.25,
              count: 3,
              wins: 1,
              losses: 2,
              winRate: 33.33,
              avgPnl: -14.08,
            },
          ]}
        />
      );
    });

    expect(container.textContent).toContain('Strategy Performance');
    expect(container.textContent).toContain('liq_sd_v1');
    expect(container.textContent).toContain('Version 1');
    expect(container.textContent).toContain('+$120.50');
    expect(container.textContent).toContain('breakout_v1');
    expect(container.textContent).toContain('Version 2');
  });
});
