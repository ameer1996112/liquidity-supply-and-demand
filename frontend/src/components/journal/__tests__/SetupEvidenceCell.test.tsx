/** @vitest-environment jsdom */

import { createRoot } from 'react-dom/client';
import { act } from 'react';
import { describe, expect, test } from 'vitest';
import { SetupEvidenceCell } from '../SetupEvidenceCell';

describe('SetupEvidenceCell', () => {
  test('shows a compact evidence icon when setup evidence exists', () => {
    const container = document.createElement('div');
    const root = createRoot(container);

    act(() => {
      root.render(
        <SetupEvidenceCell
          evidence={{
            status: 'ok',
            focus_image: { url: 'https://provider/setup.png' },
          }}
        />
      );
    });

    expect(container.querySelector('[data-testid="setup-evidence-icon"]')).not.toBeNull();
    root.unmount();
  });
});
