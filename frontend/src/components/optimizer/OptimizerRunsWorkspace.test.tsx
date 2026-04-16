/** @vitest-environment jsdom */

import { act } from 'react';
import { createRoot, Root } from 'react-dom/client';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

vi.mock('@/hooks/useOptimizerRuns', () => ({
  useOptimizerRuns: () => ({
    data: [
      {
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
        summary: { total_pairs: 2, running_pairs: 1, completed_pairs: 1, failed_pairs: 0, best_symbol: 'EURUSD', best_score: 2.1 },
      },
    ],
    isLoading: false,
  }),
  useOptimizerRun: () => ({
    data: {
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
      summary: { total_pairs: 2, running_pairs: 1, completed_pairs: 1, failed_pairs: 0, best_symbol: 'EURUSD', best_score: 2.1 },
    },
  }),
  useOptimizerRunResults: () => ({
    data: [
      { symbol: 'EURUSD', status: 'completed', metrics: { score: 2.1, net_profit: 250, win_rate: 61, profit_factor: 1.7, max_drawdown_pct: 5.1 } },
    ],
  }),
  useOptimizerRunEvents: () => ({
    data: [{ event_type: 'pair_completed', symbol: 'EURUSD', worker_id: 0, payload: {}, created_at: '2026-04-13T12:00:00Z' }],
  }),
  useCreateOptimizerRun: () => ({
    isPending: false,
    mutate: (_payload: unknown, options?: { onSuccess?: (run: { id: string }) => void }) => {
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
  });
});
