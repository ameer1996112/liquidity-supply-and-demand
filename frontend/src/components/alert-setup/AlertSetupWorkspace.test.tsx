/** @vitest-environment jsdom */

import { act } from 'react';
import { createRoot, type Root } from 'react-dom/client';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

let mockCreateBatchError: Error | null = null;

vi.mock('@/hooks/useAlertSetup', () => ({
  useAlertBatches: () => ({
    data: [
      {
        id: 'batch-2026-04-14',
        status: 'running',
        source_mode: 'approved',
        timeframe: '5m',
        selected_pairs: ['USDJPY', 'GBPUSD', 'XAUUSD'],
        summary: {
          total_pairs: 3,
          queued_pairs: 0,
          running_pairs: 1,
          completed_pairs: 1,
          failed_pairs: 0,
          skipped_pairs: 0,
          created_alerts: 1,
          best_pair: 'USDJPY',
          best_score: 18.2,
        },
      },
    ],
    isLoading: false,
  }),
  useAlertBatch: () => ({
    data: {
      id: 'batch-2026-04-14',
      status: 'running',
      source_mode: 'approved',
      timeframe: '5m',
      selected_pairs: ['USDJPY', 'GBPUSD', 'XAUUSD'],
      summary: {
        total_pairs: 3,
        queued_pairs: 0,
        running_pairs: 1,
        completed_pairs: 1,
        failed_pairs: 0,
        skipped_pairs: 0,
        created_alerts: 1,
        best_pair: 'USDJPY',
        best_score: 18.2,
      },
    },
  }),
  useAlertBatchResults: () => ({
    data: [
      { pair: 'USDJPY', status: 'completed', risk_weight: 0.75, timeframe: '5m', alert_id: 'alert-1' },
    ],
  }),
  useAlertBatchEvents: () => ({
    data: [
      {
        event_type: 'alert_created',
        batch_id: 'batch-2026-04-14',
        pair: 'USDJPY',
        payload: { alert_id: 'alert-1' },
        created_at: '2026-04-14T06:00:00Z',
      },
    ],
  }),
  useAlertApprovedConfigs: () => ({
    data: [
      {
        pair: 'USDJPY',
        timeframe: '5m',
        status: 'approved',
        rank: 1,
        risk_weight: 0.75,
        score: 24.63,
        profit_factor: 1.39,
        max_drawdown_pct: 4.06,
        source_run_id: 'run-1',
      },
      {
        pair: 'GBPUSD',
        timeframe: '5m',
        status: 'approved',
        rank: 2,
        risk_weight: 0.75,
        score: 24.38,
        profit_factor: 1.2,
        max_drawdown_pct: 9.05,
        source_run_id: 'run-1',
      },
      {
        pair: 'XAUUSD',
        timeframe: '5m',
        status: 'approved',
        rank: 3,
        risk_weight: 0.25,
        score: 27.44,
        profit_factor: 1.75,
        max_drawdown_pct: 9.38,
        source_run_id: 'run-1',
      },
    ],
  }),
  useAlertRunnerStatus: () => ({
    data: { agent_online: true, chrome_ready: true, agent_version: 'test', last_heartbeat: Date.now() / 1000 },
  }),
  useCreateAlertBatch: () => ({
    isPending: false,
    error: mockCreateBatchError,
    mutate: (_payload: unknown, options?: { onSuccess?: (batch: { id: string }) => void }) => {
      options?.onSuccess?.({ id: 'batch-2026-04-14' });
    },
  }),
  useCancelAlertBatch: () => ({
    isPending: false,
    mutate: () => {},
  }),
}));

import { AlertSetupWorkspace } from './AlertSetupWorkspace';

describe('AlertSetupWorkspace', () => {
  let container: HTMLDivElement;
  let root: Root;

  beforeEach(() => {
    mockCreateBatchError = null;
    container = document.createElement('div');
    document.body.appendChild(container);
    root = createRoot(container);
  });

  afterEach(() => {
    act(() => root.unmount());
    container.remove();
  });

  it('renders alert setup controls and batch output', () => {
    act(() => {
      root.render(<AlertSetupWorkspace />);
    });

    expect(document.body.textContent).toContain('Start batch');
    expect(document.body.textContent).toContain('Top 3');
    expect(document.body.textContent).toContain('Approved preview');
    expect(document.body.textContent).toContain('USDJPY');
    expect(document.body.textContent).toContain('Alert Setup runner');
  });

  it('shows batch creation error inline when start batch fails', () => {
    mockCreateBatchError = new Error('parallel_results.json not found');

    act(() => {
      root.render(<AlertSetupWorkspace />);
    });

    expect(document.body.textContent).toContain('Start batch failed: parallel_results.json not found');
  });
});
