import { renderToStaticMarkup } from 'react-dom/server';
import { describe, expect, it, vi } from 'vitest';

import { AccountGuardsView } from '../AccountGuardsView';
import { GuardsPanel } from '../GuardsPanel';

vi.mock('@/hooks/useGuards', () => ({
  useGlobalGuardsConfig: () => ({
    data: {
      groups: {
        capital_protection: [
          {
            guard_id: 'kill_switch',
            name: 'Kill Switch',
            description: 'desc',
            user_description: 'global guard',
            tier: 'critical',
            group: 'capital_protection',
            group_label: 'Capital Protection',
            value_type: 'bool',
            enabled: false,
            default: false,
            min_value: null,
            max_value: null,
            unit: '',
            thresholds: [],
            rejection_count_7d: 0,
            last_rejection_reason: null,
            dynamic_threshold: null,
            scope: 'global',
          },
        ],
        scheduling: [
          {
            guard_id: 'swap_guard',
            name: 'Swap / Rollover Guard',
            description: 'desc',
            user_description: 'adaptive swap guard',
            tier: 'important',
            group: 'scheduling',
            group_label: 'Scheduling',
            value_type: 'bool',
            enabled: true,
            default: true,
            min_value: null,
            max_value: null,
            unit: '',
            thresholds: [
              {
                setting_key: 'swap_time',
                name: 'Rollover Time (HH:MM)',
                value_type: 'str',
                current_value: '00:00',
                default: '00:00',
                min_value: null,
                max_value: null,
                unit: '',
              },
              {
                setting_key: 'swap_min_block_after_min',
                name: 'Minimum Block After (min)',
                value_type: 'int',
                current_value: 45,
                default: 45,
                min_value: 1,
                max_value: 360,
                unit: 'min',
              },
            ],
            rejection_count_7d: 2,
            last_rejection_reason: 'SWAP_POST_MIN_FLOOR',
            dynamic_threshold: null,
            scope: 'global',
          },
        ],
      },
      group_labels: { capital_protection: 'Capital Protection', scheduling: 'Scheduling' },
      tier_labels: {},
      total_rejections_7d: 0,
      total_signals_7d: 0,
    },
    isLoading: false,
    error: null,
  }),
  useUpdateGlobalGuard: () => ({ mutate: vi.fn() }),
  useGuardAccounts: () => ({
    data: {
      accounts: [{ id: 'acct-1', name: 'ACG-DEMO-2', run_mode: 'LIVE' }],
    },
    isLoading: false,
    error: null,
  }),
  useAccountGuardsConfig: () => ({
    data: {
      groups: {
        capital_protection: [
          {
            guard_id: 'daily_loss_limit',
            name: 'Daily Loss Limit',
            description: 'desc',
            user_description: 'account guard',
            tier: 'critical',
            group: 'capital_protection',
            group_label: 'Capital Protection',
            value_type: 'float',
            enabled: 4,
            default: 4,
            min_value: 0.5,
            max_value: 10,
            unit: '%',
            thresholds: [],
            rejection_count_7d: 0,
            last_rejection_reason: null,
            dynamic_threshold: null,
            scope: 'account',
          },
        ],
      },
      group_labels: { capital_protection: 'Capital Protection' },
      tier_labels: {},
      total_rejections_7d: 0,
      total_signals_7d: 0,
    },
    isLoading: false,
    error: null,
  }),
  useUpdateAccountGuard: () => ({ mutate: vi.fn() }),
}));

describe('GuardsPanel', () => {
  it('renders Global and Per Account sub-tabs', () => {
    const html = renderToStaticMarkup(<GuardsPanel />);

    expect(html).toContain('Global');
    expect(html).toContain('Per Account');
    expect(html).toContain('Swap / Rollover Guard');
    expect(html).toContain('Rollover Time (HH:MM)');
    expect(html).toContain('Minimum Block After (min)');
  });

  it('renders account selector and scope label in account view', () => {
    const html = renderToStaticMarkup(<AccountGuardsView />);

    expect(html).toContain('Account');
    expect(html).toContain('ACG-DEMO-2');
    expect(html).toContain('Account: ACG-DEMO-2');
  });
});
