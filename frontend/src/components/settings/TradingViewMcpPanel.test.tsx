/** @vitest-environment jsdom */

import { act } from 'react';
import { createRoot, Root } from 'react-dom/client';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { TradingViewMcpPanel } from './TradingViewMcpPanel';

globalThis.IS_REACT_ACT_ENVIRONMENT = true;

vi.mock('@/lib/api', () => ({
  fetchTradingViewMcpConfig: vi.fn(),
  patchTradingViewMcpConfig: vi.fn(),
  fetchLocalChartProviderCompatibility: vi.fn(),
}));

describe('TradingViewMcpPanel', () => {
  let container: HTMLDivElement;
  let root: Root;

  beforeEach(() => {
    container = document.createElement('div');
    document.body.appendChild(container);
    root = createRoot(container);
  });

  afterEach(() => {
    act(() => {
      root.unmount();
    });
    container.remove();
    vi.clearAllMocks();
  });

  it('loads approved versions and local compatibility status', async () => {
    const api = await import('@/lib/api');

    vi.mocked(api.fetchTradingViewMcpConfig).mockResolvedValue({
      approved_versions: ['2.9.0'],
    });
    vi.mocked(api.fetchLocalChartProviderCompatibility).mockResolvedValue({
      status: 'supported',
      chart_context_enabled: true,
      tradingview_version: '2.9.0',
      checked_at: '2026-04-21T12:00:00Z',
      reason: '',
      probe: { command: 'status', ok: true },
    });

    await act(async () => {
      root.render(<TradingViewMcpPanel />);
    });

    expect(container.textContent).toContain('TradingView MCP Compatibility');
    expect(container.textContent).toContain('2.9.0');
    expect(container.textContent).toContain('supported');
    expect(container.textContent).toContain('Current version already approved.');
  });

  it('approves the current detected TradingView version and refreshes local status', async () => {
    const api = await import('@/lib/api');

    vi.mocked(api.fetchTradingViewMcpConfig).mockResolvedValue({
      approved_versions: ['2.9.0'],
    });
    vi.mocked(api.fetchLocalChartProviderCompatibility)
      .mockResolvedValueOnce({
        status: 'unsupported_version',
        chart_context_enabled: false,
        tradingview_version: '2.9.1',
        checked_at: '2026-04-21T12:00:00Z',
        reason: 'Version is not approved yet',
        probe: { command: 'status', ok: true },
      })
      .mockResolvedValueOnce({
        status: 'supported',
        chart_context_enabled: true,
        tradingview_version: '2.9.1',
        checked_at: '2026-04-21T12:01:00Z',
        reason: '',
        probe: { command: 'status', ok: true },
      });
    vi.mocked(api.patchTradingViewMcpConfig).mockResolvedValue({
      approved_versions: ['2.9.0', '2.9.1'],
    });

    await act(async () => {
      root.render(<TradingViewMcpPanel />);
    });

    const approveButton = container.querySelector(
      '[data-testid="tradingview-mcp-approve-button"]'
    ) as HTMLButtonElement | null;

    expect(approveButton).not.toBeNull();
    expect(approveButton?.disabled).toBe(false);

    await act(async () => {
      approveButton?.dispatchEvent(new MouseEvent('click', { bubbles: true }));
    });

    expect(api.patchTradingViewMcpConfig).toHaveBeenCalledWith({
      approved_versions: ['2.9.0', '2.9.1'],
    });
    expect(api.fetchLocalChartProviderCompatibility).toHaveBeenCalledTimes(2);
    expect(container.textContent).toContain(
      'Approved 2.9.1 for local TradingView MCP use.'
    );
  });

  it('keeps approval available when the local probe fails but the version is known', async () => {
    const api = await import('@/lib/api');

    vi.mocked(api.fetchTradingViewMcpConfig).mockResolvedValue({
      approved_versions: [],
    });
    vi.mocked(api.fetchLocalChartProviderCompatibility).mockResolvedValue({
      status: 'probe_failed',
      chart_context_enabled: false,
      tradingview_version: '2.9.2',
      checked_at: '2026-04-21T12:00:00Z',
      reason: 'status command failed',
      probe: { command: 'status', ok: false, error: 'exit 1' },
    });

    await act(async () => {
      root.render(<TradingViewMcpPanel />);
    });

    const approveButton = container.querySelector(
      '[data-testid="tradingview-mcp-approve-button"]'
    ) as HTMLButtonElement | null;

    expect(container.textContent).toContain('probe failed');
    expect(container.textContent).toContain('2.9.2');
    expect(approveButton).not.toBeNull();
    expect(approveButton?.disabled).toBe(false);
  });
});
