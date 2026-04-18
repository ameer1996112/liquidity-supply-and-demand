/** @vitest-environment jsdom */

import { act } from 'react';
import { createRoot, Root } from 'react-dom/client';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

const createRunMutate = vi.fn();

const runFixture = {
  'run-2026-04-13': {
    id: 'run-2026-04-13',
    strategy_id: 'liq_sd_v1',
    strategy_version: '1',
    status: 'running',
    mode: 'bayesian',
    workers: 2,
    pairs: ['EURUSD', 'GBPUSD'],
    n_trials: 25,
    dd_limit: 6,
    dry_run: true,
    broker: 'vantage',
    market: 'forex',
    summary: { total_pairs: 2, running_pairs: 1, completed_pairs: 1, failed_pairs: 0, best_symbol: 'EURUSD', best_score: 2.1 },
    portfolio_result: {
      combined_max_drawdown_pct: 4.8,
      combined_daily_drawdown_pct: 2.1,
      worst_day_pct: -1.4,
      weights: { EURUSD: 0.6, GBPUSD: 0.4 },
    },
  },
  'run-2026-04-11': {
    id: 'run-2026-04-11',
    strategy_id: 'liq_sd_v1',
    strategy_version: '0.9',
    status: 'completed',
    mode: 'smart',
    workers: 1,
    pairs: ['USDJPY'],
    n_trials: 12,
    dd_limit: 5,
    dry_run: true,
    broker: 'fxcm',
    market: 'forex',
    summary: { total_pairs: 1, running_pairs: 0, completed_pairs: 1, failed_pairs: 0, best_symbol: 'USDJPY', best_score: 1.6 },
    portfolio_result: {
      combined_max_drawdown_pct: 3.2,
      combined_daily_drawdown_pct: 1.2,
      worst_day_pct: -0.8,
      weights: { USDJPY: 1 },
    },
  },
  'run-2026-04-10': {
    id: 'run-2026-04-10',
    strategy_id: 'liq_sd_v1',
    strategy_version: '0.8',
    status: 'completed',
    mode: 'fast',
    workers: 1,
    pairs: ['AUDUSD'],
    n_trials: 8,
    dd_limit: 5,
    dry_run: true,
    broker: 'oanda',
    market: 'forex',
    summary: { total_pairs: 1, running_pairs: 0, completed_pairs: 1, failed_pairs: 0, best_symbol: 'AUDUSD', best_score: 1.1 },
    portfolio_result: {
      combined_max_drawdown_pct: 2.4,
      combined_daily_drawdown_pct: 0.9,
      worst_day_pct: -0.4,
      weights: {},
    },
  },
} as const;

const resultFixture = {
  'run-2026-04-13': [
    {
      symbol: 'EURUSD',
      status: 'completed',
      metrics: { score: 2.1, net_profit: 250, win_rate: 61, profit_factor: 1.7, max_drawdown_pct: 5.1, total_trades: 19 },
      validation_metrics: { score: 1.8, profit_factor: 1.4, max_drawdown_pct: 4.2 },
      forward_metrics: { score: 1.6, profit_factor: 1.3, max_drawdown_pct: 4.6 },
    },
    {
      symbol: 'GBPUSD',
      status: 'completed',
      metrics: { score: 1.3, net_profit: 120, win_rate: 54, profit_factor: 1.2, max_drawdown_pct: 5.7, total_trades: 14 },
    },
  ],
  'run-2026-04-11': [
    {
      symbol: 'USDJPY',
      status: 'completed',
      metrics: { score: 1.6, net_profit: 90, win_rate: 55, profit_factor: 1.25, max_drawdown_pct: 3.1, total_trades: 12 },
    },
  ],
  'run-2026-04-10': [
    {
      symbol: 'AUDUSD',
      status: 'completed',
      metrics: { score: 1.1, net_profit: 35, win_rate: 51, profit_factor: 1.05, max_drawdown_pct: 2.4, total_trades: 9 },
    },
  ],
} as const;

const trialFixture = {
  'run-2026-04-13:EURUSD': [
    {
      id: 'trial-1',
      symbol: 'EURUSD',
      trial_number: 7,
      window: 'validation',
      metrics: { score: 1.8, profit_factor: 1.4, max_drawdown_pct: 4.2 },
    },
  ],
} as const;

const stressFixture = {
  'run-2026-04-13:EURUSD': [
    {
      id: 'stress-1',
      symbol: 'EURUSD',
      scenario: 'spread_125',
      status: 'pass',
      metrics: { max_drawdown_pct: 4.9, profit_factor: 1.18 },
    },
  ],
} as const;

vi.mock('@/hooks/useOptimizerRuns', () => ({
  useOptimizerRuns: () => ({
    data: [runFixture['run-2026-04-13'], runFixture['run-2026-04-11'], runFixture['run-2026-04-10']],
    isLoading: false,
  }),
  useOptimizerRun: (runId: string | null) => ({
    data: runFixture[(runId ?? 'run-2026-04-13') as keyof typeof runFixture] ?? runFixture['run-2026-04-13'],
  }),
  useOptimizerRunResults: (runId: string | null) => ({
    data: resultFixture[(runId ?? 'run-2026-04-13') as keyof typeof resultFixture] ?? resultFixture['run-2026-04-13'],
  }),
  useOptimizerRunEvents: () => ({
    data: [{ event_type: 'pair_completed', symbol: 'EURUSD', worker_id: 0, payload: {}, created_at: '2026-04-13T12:00:00Z' }],
  }),
  useOptimizerRunTrials: (runId: string | null, symbol?: string | null) => ({
    data: runId && symbol ? trialFixture[`${runId}:${symbol}` as keyof typeof trialFixture] ?? [] : [],
  }),
  useOptimizerRunStressResults: (runId: string | null, symbol?: string | null) => ({
    data: runId && symbol ? stressFixture[`${runId}:${symbol}` as keyof typeof stressFixture] ?? [] : [],
  }),
  useCreateOptimizerRun: () => ({
    isPending: false,
    mutate: (payload: unknown, options?: { onSuccess?: (run: { id: string }) => void }) => {
      createRunMutate(payload);
      options?.onSuccess?.({ id: 'run-2026-04-13' });
    },
  }),
  useAgentStatus: () => ({
    data: { agent_online: true, chrome_ready: true, agent_version: 'test', last_heartbeat: Date.now() / 1000 },
  }),
  useCancelOptimizerRun: () => ({
    isPending: false,
    mutate: () => {},
  }),
}));

import { OptimizerRunsWorkspace } from './OptimizerRunsWorkspace';

describe('OptimizerRunsWorkspace', () => {
  let container: HTMLDivElement;
  let root: Root;

  beforeEach(() => {
    createRunMutate.mockClear();
    container = document.createElement('div');
    document.body.appendChild(container);
    root = createRoot(container);
  });

  afterEach(() => {
    act(() => root.unmount());
    container.remove();
  });

  it('renders running summary and results', () => {
    act(() => {
      root.render(<OptimizerRunsWorkspace />);
    });

    expect(document.body.textContent).toContain('Start run');
    expect(document.body.textContent).toContain('running');
    expect(document.body.textContent).toContain('Completed pairs');
    expect(document.body.textContent).toContain('EURUSD');
    expect(document.body.textContent).toContain('liq_sd_v1@1');
    expect(document.body.textContent).toContain('VANTAGE');
    expect(document.body.textContent).toContain('Portfolio overview');
    expect(document.body.textContent).toContain('Pair analysis');
  });

  it('renders portfolio overview metrics from enriched run payload', async () => {
    act(() => {
      root.render(<OptimizerRunsWorkspace />);
    });

    await expect.poll(() => document.body.textContent ?? '').toMatch(/combined max dd/i);
    expect(document.body.textContent).toContain('4.80%');
    expect(document.body.textContent).toContain('0 approved · 2 reduced · 0 rejected');
    expect(document.body.textContent).toContain('EURUSD 60%');
  });

  it('defaults broker selection to Vantage and submits selected broker', () => {
    act(() => {
      root.render(<OptimizerRunsWorkspace />);
    });

    const brokerSelect = container.querySelector('select[aria-label="Broker"]') as HTMLSelectElement | null;
    expect(brokerSelect?.value).toBe('vantage');

    act(() => {
      if (brokerSelect) {
        brokerSelect.value = 'oanda';
        brokerSelect.dispatchEvent(new Event('change', { bubbles: true }));
      }
    });

    const startButton = Array.from(container.querySelectorAll('button')).find((button) =>
      button.textContent?.includes('Start run')
    );

    act(() => {
      startButton?.dispatchEvent(new MouseEvent('click', { bubbles: true }));
    });

    expect(createRunMutate).toHaveBeenCalledWith(
      expect.objectContaining({
        broker: 'oanda',
      })
    );
  });

  it('renders analyst drill-down content and run comparison selection', () => {
    act(() => {
      root.render(<OptimizerRunsWorkspace />);
    });

    expect(document.body.textContent).toContain('EURUSD drill-down');
    expect(document.body.textContent).toContain('Decision reason');
    expect(document.body.textContent).toContain('Reduced risk because EURUSD still holds a 60% allocation');
    expect(document.body.textContent).toContain('Validation context');
    expect(document.body.textContent).toContain('Forward context');
    expect(document.body.textContent).toContain('spread_125');
    expect(document.body.textContent).toContain('Run comparison & history');

    const historyButton = Array.from(container.querySelectorAll('button')).find((button) =>
      button.textContent?.includes('run-2026-04-11')
    );

    act(() => {
      historyButton?.dispatchEvent(new MouseEvent('click', { bubbles: true }));
    });

    expect(document.body.textContent).toContain('USDJPY drill-down');
    expect(document.body.textContent).toContain('Approved because USDJPY kept a 100% portfolio weight');
    expect(document.body.textContent).toContain('3.20%');
    expect(document.body.textContent).not.toContain('EURUSD drill-down');
    expect(document.body.textContent).not.toContain('spread_125');
  });

  it('shows unresolved pair decisions when no allocator weight is available', () => {
    act(() => {
      root.render(<OptimizerRunsWorkspace />);
    });

    const historyButton = Array.from(container.querySelectorAll('button')).find((button) =>
      button.textContent?.includes('run-2026-04-10')
    );

    act(() => {
      historyButton?.dispatchEvent(new MouseEvent('click', { bubbles: true }));
    });

    expect(document.body.textContent).toContain('AUDUSD drill-down');
    expect(document.body.textContent).toContain('1 unresolved');
    expect(document.body.textContent).toContain('Pending review because AUDUSD finished its pair run');
    expect(document.body.textContent).not.toContain('1 rejected');
  });
});
