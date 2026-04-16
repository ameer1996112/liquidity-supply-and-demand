/** @vitest-environment jsdom */

import { createRoot } from 'react-dom/client';
import { act } from 'react';
import { describe, expect, test } from 'vitest';
import { SetupEvidenceCell } from '../SetupEvidenceCell';

describe('SetupEvidenceCell', () => {
  test('shows a positive setup icon when evidence is ok', () => {
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

    const icon = container.querySelector('[data-testid="setup-evidence-icon"]');
    expect(icon?.getAttribute('aria-label')).toBe('Setup evidence ok');
    expect(icon?.className).toContain('text-emerald-400');
    root.unmount();
  });

  test('shows a warning setup icon when evidence is degraded', () => {
    const container = document.createElement('div');
    const root = createRoot(container);

    act(() => {
      root.render(
        <SetupEvidenceCell
          evidence={{
            status: 'degraded',
            reason: 'fallback crop',
          }}
        />
      );
    });

    const icon = container.querySelector('[data-testid="setup-evidence-icon"]');
    expect(icon?.getAttribute('aria-label')).toBe('Setup evidence degraded');
    expect(icon?.className).toContain('text-amber-400');
    root.unmount();
  });

  test('shows a muted setup icon when evidence is missing', () => {
    const container = document.createElement('div');
    const root = createRoot(container);

    act(() => {
      root.render(<SetupEvidenceCell evidence={null} />);
    });

    const icon = container.querySelector('[data-testid="setup-evidence-icon"]');
    expect(icon?.getAttribute('aria-label')).toBe('Setup evidence missing');
    expect(icon?.className).toContain('text-[var(--to-text-dim)]');
    root.unmount();
  });
});
