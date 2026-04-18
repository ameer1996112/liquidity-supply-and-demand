/** @vitest-environment jsdom */

import { act } from 'react';
import { createRoot, Root } from 'react-dom/client';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';

import type { OptimizerRunApi } from '@/lib/api';
import {
  fetchAgentStatus,
  fetchOptimizerRun,
  fetchOptimizerRunEvents,
  fetchOptimizerRunResults,
  fetchOptimizerRunStressResults,
  fetchOptimizerRunTrials,
  fetchOptimizerRuns,
} from '@/lib/api';
import { optimizerRunKeys, useOptimizerRunResults } from './useOptimizerRuns';

vi.mock('@/lib/api', async () => {
  const actual = await vi.importActual<typeof import('@/lib/api')>('@/lib/api');
  return {
    ...actual,
    fetchAgentStatus: vi.fn(),
    fetchOptimizerRun: vi.fn(),
    fetchOptimizerRunEvents: vi.fn(),
    fetchOptimizerRunResults: vi.fn(),
    fetchOptimizerRunStressResults: vi.fn(),
    fetchOptimizerRunTrials: vi.fn(),
    fetchOptimizerRuns: vi.fn(),
  };
});

const mockedFetchOptimizerRunResults = vi.mocked(fetchOptimizerRunResults);
const mockedFetchOptimizerRuns = vi.mocked(fetchOptimizerRuns);
const mockedFetchOptimizerRun = vi.mocked(fetchOptimizerRun);
const mockedFetchOptimizerRunEvents = vi.mocked(fetchOptimizerRunEvents);
const mockedFetchOptimizerRunTrials = vi.mocked(fetchOptimizerRunTrials);
const mockedFetchOptimizerRunStressResults = vi.mocked(fetchOptimizerRunStressResults);
const mockedFetchAgentStatus = vi.mocked(fetchAgentStatus);

function ResultsHarness({ runId }: { runId: string }) {
  const { data = [] } = useOptimizerRunResults(runId);
  return (
    <div data-testid='results-state'>
      {data.map((result) => `${result.symbol}:${result.metrics?.score ?? '--'}`).join('|') || 'empty'}
    </div>
  );
}

describe('useOptimizerRunResults cache seeding', () => {
  let container: HTMLDivElement;
  let root: Root;

  beforeEach(() => {
    container = document.createElement('div');
    document.body.appendChild(container);
    root = createRoot(container);
    mockedFetchOptimizerRuns.mockResolvedValue([]);
    mockedFetchOptimizerRun.mockRejectedValue(new Error('not used'));
    mockedFetchOptimizerRunEvents.mockResolvedValue([]);
    mockedFetchOptimizerRunTrials.mockResolvedValue([]);
    mockedFetchOptimizerRunStressResults.mockResolvedValue([]);
    mockedFetchAgentStatus.mockResolvedValue({
      agent_online: true,
      chrome_ready: true,
      agent_version: 'test',
      last_heartbeat: Date.now() / 1000,
    });
  });

  afterEach(() => {
    act(() => {
      root.unmount();
    });
    container.remove();
    vi.clearAllMocks();
  });

  it('boots from embedded run detail cache and then refreshes from the polled endpoint', async () => {
    const queryClient = new QueryClient({
      defaultOptions: {
        queries: {
          retry: false,
          gcTime: Infinity,
        },
      },
    });

    const cachedRun: OptimizerRunApi = {
      id: 'run-1',
      strategy_id: 'liq_sd_v1',
      strategy_version: '1',
      status: 'running',
      mode: 'bayesian',
      workers: 2,
      pairs: ['EURUSD'],
      n_trials: 25,
      dd_limit: 6,
      dry_run: true,
      broker: 'vantage',
      market: 'forex',
      summary: { total_pairs: 1, running_pairs: 1, completed_pairs: 0, failed_pairs: 0 },
      results: [
        {
          symbol: 'EURUSD',
          status: 'completed',
          metrics: { score: 1.1 },
        },
      ],
    };

    queryClient.setQueryData(optimizerRunKeys.detail('run-1'), cachedRun);
    mockedFetchOptimizerRunResults.mockResolvedValue([
      {
        symbol: 'EURUSD',
        status: 'completed',
        metrics: { score: 2.6 },
      },
    ]);

    act(() => {
      root.render(
        <QueryClientProvider client={queryClient}>
          <ResultsHarness runId='run-1' />
        </QueryClientProvider>
      );
    });

    expect(container.textContent).toContain('EURUSD:1.1');
    await expect.poll(() => container.textContent ?? '').toContain('EURUSD:2.6');
    expect(mockedFetchOptimizerRunResults).toHaveBeenCalledWith('run-1');
  });

  it('accepts an empty authoritative refresh after bootstrapping from embedded cache', async () => {
    const queryClient = new QueryClient({
      defaultOptions: {
        queries: {
          retry: false,
          gcTime: Infinity,
        },
      },
    });

    const cachedRun: OptimizerRunApi = {
      id: 'run-2',
      strategy_id: 'liq_sd_v1',
      strategy_version: '1',
      status: 'running',
      mode: 'bayesian',
      workers: 2,
      pairs: ['GBPUSD'],
      n_trials: 25,
      dd_limit: 6,
      dry_run: true,
      broker: 'vantage',
      market: 'forex',
      summary: { total_pairs: 1, running_pairs: 1, completed_pairs: 0, failed_pairs: 0 },
      results: [
        {
          symbol: 'GBPUSD',
          status: 'completed',
          metrics: { score: 1.4 },
        },
      ],
    };

    queryClient.setQueryData(optimizerRunKeys.detail('run-2'), cachedRun);
    mockedFetchOptimizerRunResults.mockResolvedValueOnce([]);

    act(() => {
      root.render(
        <QueryClientProvider client={queryClient}>
          <ResultsHarness runId='run-2' />
        </QueryClientProvider>
      );
    });

    expect(container.textContent).toContain('GBPUSD:1.4');
    await expect.poll(() => container.textContent ?? '').toContain('empty');
    expect(mockedFetchOptimizerRunResults).toHaveBeenCalledWith('run-2');
  });
});
