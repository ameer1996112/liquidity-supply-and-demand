/** @vitest-environment jsdom */

import { act } from 'react';
import { createRoot, Root } from 'react-dom/client';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

const createRunMutate = vi.fn();
let agentStatusFixture = {
  agent_online: true,
  desktop_ready: true,
  chrome_ready: true,
  agent_version: 'test',
  last_heartbeat: Date.now() / 1000,
};

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
    summary: {
      total_pairs: 2,
      running_pairs: 1,
      completed_pairs: 1,
      failed_pairs: 0,
      best_symbol: 'EURUSD',
      best_score: 2.1,
      backtest_range: 'custom',
      custom_start_date: '2025-04-01',
      custom_end_date: '2026-04-01',
    },
    portfolio_result: {
      combined_max_drawdown_pct: 4.8,
      combined_daily_drawdown_pct: 2.1,
      worst_day_pct: -1.4,
      weights: { EURUSD: 0.6, GBPUSD: 0.4 },
    },
    results: [
      {
        symbol: 'EURUSD',
        status: 'completed',
        decision: 'reduce_risk',
        reason: 'forward window held, but stress DD is still too close to the cap',
        metrics: { score: 2.1, net_profit: 250, win_rate: 61, profit_factor: 1.7, max_drawdown_pct: 5.1, total_trades: 19 },
        validation_metrics: { score: 1.8, profit_factor: 1.4, max_drawdown_pct: 4.2 },
        forward_metrics: { score: 1.6, profit_factor: 1.3, max_drawdown_pct: 4.6 },
      },
      {
        symbol: 'GBPUSD',
        status: 'completed',
        decision: 'reduce_risk',
        reason: 'weight kept small because validation drifted lower than forward',
        metrics: { score: 1.3, net_profit: 120, win_rate: 54, profit_factor: 1.2, max_drawdown_pct: 5.7, total_trades: 14 },
      },
    ],
    artifacts: {
      trials: [
        {
          id: 'trial-1',
          symbol: 'EURUSD',
          trial_number: 7,
          window: 'validation',
          metrics: { score: 1.8, profit_factor: 1.4, max_drawdown_pct: 4.2 },
        },
      ],
      stress_results: [
        {
          id: 'stress-1',
          symbol: 'EURUSD',
          scenario: 'spread_125',
          status: 'pass',
          metrics: { max_drawdown_pct: 4.9, profit_factor: 1.18 },
        },
      ],
      events: [
        { event_type: 'pair_completed', symbol: 'EURUSD', worker_id: 0, payload: {}, created_at: '2026-04-13T12:00:00Z' },
      ],
      summary: {
        trial_count: 1,
        stress_result_count: 1,
        event_count: 1,
        symbols: {
          EURUSD: { trial_count: 1, stress_result_count: 1, latest_event_type: 'pair_completed' },
        },
      },
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
    results: [
      {
        symbol: 'USDJPY',
        status: 'completed',
        decision: 'pass',
        reason: 'embedded reason should lose to the fresher polled result',
        metrics: { score: 1.6, net_profit: 90, win_rate: 55, profit_factor: 1.25, max_drawdown_pct: 3.1, total_trades: 12 },
      },
    ],
    artifacts: {
      trials: [{ id: 'embedded-trial-1', symbol: 'USDJPY', trial_number: 2, window: 'validation', metrics: { score: 1.3 } }],
      stress_results: [{ id: 'embedded-stress-1', symbol: 'USDJPY', scenario: 'embedded_shock', status: 'warn' }],
      events: [],
      summary: { trial_count: 1, stress_result_count: 1, event_count: 0, symbols: { USDJPY: { trial_count: 1, stress_result_count: 1, latest_event_type: null } } },
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
    results: [
      {
        symbol: 'AUDUSD',
        status: 'completed',
        metrics: { score: 1.1, net_profit: 35, win_rate: 51, profit_factor: 1.05, max_drawdown_pct: 2.4, total_trades: 9 },
      },
    ],
    artifacts: {
      trials: [],
      stress_results: [],
      events: [],
      summary: { trial_count: 0, stress_result_count: 0, event_count: 0, symbols: {} },
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
      decision: 'pass',
      reason: 'polled result won and latest forward window stayed under both portfolio safety caps',
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
  'run-2026-04-11:USDJPY': [
    {
      id: 'trial-2',
      symbol: 'USDJPY',
      trial_number: 2,
      window: 'validation',
      metrics: { score: 1.4, profit_factor: 1.18, max_drawdown_pct: 3.4 },
    },
    {
      id: 'trial-3',
      symbol: 'USDJPY',
      trial_number: 4,
      window: 'forward',
      metrics: { score: 1.6, profit_factor: 1.25, max_drawdown_pct: 3.1 },
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
  'run-2026-04-11:USDJPY': [
    {
      id: 'stress-2',
      symbol: 'USDJPY',
      scenario: 'session_guard',
      status: 'warn',
      metrics: { max_drawdown_pct: 3.4, profit_factor: 1.1 },
    },
    {
      id: 'stress-3',
      symbol: 'USDJPY',
      scenario: 'live_refresh',
      status: 'pass',
      metrics: { max_drawdown_pct: 3.0, profit_factor: 1.22 },
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
    data: runId === 'run-2026-04-13' ? [] : resultFixture[(runId ?? 'run-2026-04-13') as keyof typeof resultFixture] ?? [],
    isFetchedAfterMount: runId === 'run-2026-04-11',
  }),
  useOptimizerRunEvents: () => ({
    data: [],
    isFetchedAfterMount: false,
  }),
  useOptimizerRunTrials: (runId: string | null, symbol?: string | null) => ({
    data: runId === 'run-2026-04-13' ? [] : runId && symbol ? trialFixture[`${runId}:${symbol}` as keyof typeof trialFixture] ?? [] : [],
    isFetchedAfterMount: runId === 'run-2026-04-11',
  }),
  useOptimizerRunStressResults: (runId: string | null, symbol?: string | null) => ({
    data: runId === 'run-2026-04-13' ? [] : runId && symbol ? stressFixture[`${runId}:${symbol}` as keyof typeof stressFixture] ?? [] : [],
    isFetchedAfterMount: runId === 'run-2026-04-11',
  }),
  useCreateOptimizerRun: () => ({
    isPending: false,
    mutate: (payload: unknown, options?: { onSuccess?: (run: { id: string }) => void }) => {
      createRunMutate(payload);
      options?.onSuccess?.({ id: 'run-2026-04-13' });
    },
  }),
  useAgentStatus: () => ({
    data: agentStatusFixture,
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
    agentStatusFixture = {
      agent_online: true,
      desktop_ready: true,
      chrome_ready: true,
      agent_version: 'test',
      last_heartbeat: Date.now() / 1000,
    };
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
    const backtestRangeSelect = container.querySelector('select[aria-label="Backtest range"]') as HTMLSelectElement | null;
    expect(backtestRangeSelect?.value).toBe('365d');

    act(() => {
      if (brokerSelect) {
        brokerSelect.value = 'oanda';
        brokerSelect.dispatchEvent(new Event('change', { bubbles: true }));
      }
      if (backtestRangeSelect) {
        backtestRangeSelect.value = '90d';
        backtestRangeSelect.dispatchEvent(new Event('change', { bubbles: true }));
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
        backtest_range: '90d',
      })
    );
  });

  it('shows custom range helper and source overlap warning for validate mode', () => {
    act(() => {
      root.render(<OptimizerRunsWorkspace />);
    });

    const modeSelect = Array.from(container.querySelectorAll('select')).find((select) =>
      select.textContent?.includes('Validate')
    ) as HTMLSelectElement | undefined;
    const backtestRangeSelect = container.querySelector('select[aria-label="Backtest range"]') as HTMLSelectElement | null;

    act(() => {
      if (modeSelect) {
        modeSelect.value = 'validate';
        modeSelect.dispatchEvent(new Event('change', { bubbles: true }));
      }
      if (backtestRangeSelect) {
        backtestRangeSelect.value = 'custom';
        backtestRangeSelect.dispatchEvent(new Event('change', { bubbles: true }));
      }
    });

    const sourceInput = container.querySelector('input[aria-label="Source run ID"]') as HTMLInputElement | null;
    const startInput = container.querySelector('input[aria-label="Custom start date"]') as HTMLInputElement | null;
    const endInput = container.querySelector('input[aria-label="Custom end date"]') as HTMLInputElement | null;

    act(() => {
      if (sourceInput) {
        sourceInput.value = 'run-2026-04-13';
        sourceInput.dispatchEvent(new Event('input', { bubbles: true }));
      }
      if (startInput) {
        startInput.value = '2025-03-01';
        startInput.dispatchEvent(new Event('input', { bubbles: true }));
      }
      if (endInput) {
        endInput.value = '2025-05-01';
        endInput.dispatchEvent(new Event('input', { bubbles: true }));
      }
    });

    expect(document.body.textContent).toContain('For walk-forward validation');
    expect(document.body.textContent).toContain("overlaps with the source run's window");
    expect(document.body.textContent).not.toContain('Trials');
  });

  it('renders desktop bridge offline when the desktop automation bridge is unavailable', () => {
    agentStatusFixture = {
      agent_online: true,
      desktop_ready: false,
      chrome_ready: false,
      agent_version: 'test',
      last_heartbeat: Date.now() / 1000,
    };

    act(() => {
      root.render(<OptimizerRunsWorkspace />);
    });

    expect(document.body.textContent).toContain('Desktop Bridge Offline');
    expect(document.body.textContent).not.toContain('Chrome Offline');
  });

  it('renders analyst drill-down content and run comparison selection', () => {
    act(() => {
      root.render(<OptimizerRunsWorkspace />);
    });

    expect(document.body.textContent).toContain('EURUSD drill-down');
    expect(document.body.textContent).toContain('Decision reason');
    expect(document.body.textContent).toContain('forward window held, but stress DD is still too close to the cap');
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
    expect(document.body.textContent).toContain('polled result won and latest forward window stayed under both portfolio safety caps');
    expect(document.body.textContent).toContain('3.20%');
    expect(document.body.textContent).not.toContain('EURUSD drill-down');
    expect(document.body.textContent).toContain('Trial #4');
    expect(document.body.textContent).toContain('live_refresh');
    expect(document.body.textContent).not.toContain('embedded_shock');
    expect(document.body.textContent).toContain('Top trial #4');
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

  it('renders saved run details from enriched API payload when side queries are sparse', () => {
    act(() => {
      root.render(<OptimizerRunsWorkspace />);
    });

    expect(document.body.textContent).toContain('Portfolio overview');
    expect(document.body.textContent).toContain('Pair analysis');
    expect(document.body.textContent).toContain('forward window held, but stress DD is still too close to the cap');
    expect(document.body.textContent).toContain('spread_125');
    expect(document.body.textContent).toContain('Run events');
  });
});
