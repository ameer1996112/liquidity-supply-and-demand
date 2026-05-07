/** @vitest-environment jsdom */

import { createRoot } from 'react-dom/client';
import { act } from 'react';
import { describe, expect, test } from 'vitest';
import { SetupEvidenceDetail } from '../SetupEvidenceDetail';

describe('SetupEvidenceDetail', () => {
  test('renders screenshot and pine snapshot summary', () => {
    const container = document.createElement('div');
    const root = createRoot(container);

    act(() => {
      root.render(
        <SetupEvidenceDetail
          evidence={{
            status: 'ok',
            focus_zone: { label: 'Demand', low: 0.7149, high: 0.7153 },
            focus_image: { url: 'https://provider/setup.png' },
            pine_snapshot: { zone_count: 1, label_count: 2, top_labels: ['LONG'] },
            reason: '',
          }}
        />
      );
    });

    expect(
      container.querySelector('img[alt="Setup evidence preview"]')?.getAttribute('src')
    ).toBe('https://provider/setup.png');
    expect(container.textContent).toContain('Demand');
    expect(container.textContent).toContain('LONG');
    expect(container.textContent).toContain('ok');
    expect(container.querySelector('button[aria-label="Open setup evidence"]')).not.toBeNull();
    root.unmount();
  });

  test('renders degraded reason without modal trigger when image is unavailable', () => {
    const container = document.createElement('div');
    const root = createRoot(container);

    act(() => {
      root.render(
        <SetupEvidenceDetail
          evidence={{
            status: 'degraded',
            reason: 'Focus image unavailable',
            pine_snapshot: { zone_count: 0, label_count: 0, top_labels: [] },
          }}
        />
      );
    });

    expect(container.textContent).toContain('degraded');
    expect(container.textContent).toContain('Focus image unavailable');
    expect(container.querySelector('button[aria-label="Open setup evidence"]')).toBeNull();
    root.unmount();
  });

  test('renders zone setup fallback when mcp image evidence is missing', () => {
    const container = document.createElement('div');
    const root = createRoot(container);

    act(() => {
      root.render(
        <SetupEvidenceDetail
          evidence={null}
          fallback={{
            symbol: 'GBPNZD',
            zoneType: 'supply',
            zoneGrade: 'A+',
            entryModel: 'dir_close',
            session: 1,
            entry: 2.28128,
            stopLoss: 2.28216,
            takeProfit: 2.27908,
            slPips: 8.8,
            score: 70,
            rrRatio: 2.5,
          }}
        />
      );
    });

    expect(container.textContent).toContain('zone setup');
    expect(container.textContent).toContain('SUPPLY A+');
    expect(container.textContent).toContain('DIR_CLOSE');
    expect(container.textContent).toContain('London');
    expect(container.textContent).toContain('2.28128 / 2.28216 / 2.27908');
    expect(container.textContent).not.toContain('Setup evidence unavailable');
    root.unmount();
  });

  test('formats evidence zone prices using the fallback symbol precision', () => {
    const container = document.createElement('div');
    const root = createRoot(container);

    act(() => {
      root.render(
        <SetupEvidenceDetail
          evidence={{
            status: 'degraded',
            focus_zone: { label: 'SUPPLY-18981', low: 4743.55, high: 4750.34 },
            reason: 'visual chart screenshot was blank or still loading',
            pine_snapshot: { zone_count: 0, label_count: 0, top_labels: [] },
          }}
          fallback={{
            symbol: 'XAUUSD',
          }}
        />
      );
    });

    expect(container.textContent).toContain('SUPPLY-18981 4743.55 - 4750.34');
    expect(container.textContent).not.toContain('4743.5500');
    root.unmount();
  });
});
