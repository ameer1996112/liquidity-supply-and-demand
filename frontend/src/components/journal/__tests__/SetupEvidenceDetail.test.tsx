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
      container.querySelector('img[alt="Setup evidence"]')?.getAttribute('src')
    ).toBe('https://provider/setup.png');
    expect(container.textContent).toContain('Demand');
    expect(container.textContent).toContain('LONG');
    root.unmount();
  });
});
