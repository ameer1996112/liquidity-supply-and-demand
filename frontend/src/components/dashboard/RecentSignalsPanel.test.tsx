/** @vitest-environment jsdom */

import { useState } from 'react';
import { createRoot, Root } from 'react-dom/client';
import { act } from 'react';
import { beforeEach, afterEach, describe, expect, it, vi } from 'vitest';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { RecentSignalsPanel } from './RecentSignalsPanel';
import { SignalInspector } from '@/components/SignalInspector';
import type { TradingSignal } from '@/types/trading';
import { useTradingSignals } from '@/hooks/useTradingSignals';

vi.mock('@/hooks/useTradingSignals', () => ({
  useTradingSignals: vi.fn(),
}));

const mockedUseTradingSignals = vi.mocked(useTradingSignals);

const signalFixture: TradingSignal = {
  id: 'sig-1',
  created_at: '2026-02-20T10:00:00.000Z',
  symbol: 'USDJPY',
  side: 'buy',
  status: 'ai_rejected',
  price: 155.458,
};

function DashboardHarness() {
  const [selectedSignal, setSelectedSignal] = useState<TradingSignal | null>(
    null
  );
  const [inspectorOpen, setInspectorOpen] = useState(false);

  const queryClient = new QueryClient();
  return (
    <QueryClientProvider client={queryClient}>
      <RecentSignalsPanel
        onSelectSignal={(signal) => {
          setSelectedSignal(signal);
          setInspectorOpen(true);
        }}
      />
      <SignalInspector
        signal={selectedSignal}
        open={inspectorOpen}
        onOpenChange={setInspectorOpen}
      />
    </QueryClientProvider>
  );
}

describe('RecentSignalsPanel drawer behavior', () => {
  let container: HTMLDivElement;
  let root: Root;

  beforeEach(() => {
    class ResizeObserverMock {
      observe() {}
      unobserve() {}
      disconnect() {}
    }

    vi.stubGlobal('ResizeObserver', ResizeObserverMock);
    mockedUseTradingSignals.mockReturnValue({
      data: [signalFixture],
      isLoading: false,
    } as ReturnType<typeof useTradingSignals>);

    container = document.createElement('div');
    document.body.appendChild(container);
    root = createRoot(container);
  });

  afterEach(() => {
    act(() => {
      root.unmount();
    });
    container.remove();
    vi.unstubAllGlobals();
    vi.clearAllMocks();
  });

  it('opens only the SignalInspector drawer and not the legacy Signal details panel on row click', () => {
    act(() => {
      root.render(<DashboardHarness />);
    });

    const row = container.querySelector('.data-row') as HTMLDivElement | null;
    expect(row).not.toBeNull();

    act(() => {
      row?.dispatchEvent(new MouseEvent('click', { bubbles: true }));
    });

    const inspectorDrawer = document.querySelector(
      '[data-testid="signal-inspector-drawer"]'
    );

    expect(inspectorDrawer).not.toBeNull();
    expect(inspectorDrawer?.className).toContain('bg-background');
    expect(inspectorDrawer?.className).toContain('border-border');
    expect(inspectorDrawer?.className).not.toContain('bg-zinc-950');
    expect(
      document.querySelector('[data-testid="legacy-signal-details-panel"]')
    ).toBeNull();
  });
});
