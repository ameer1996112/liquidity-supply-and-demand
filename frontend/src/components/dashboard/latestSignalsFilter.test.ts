import { describe, expect, it } from 'vitest';
import {
  buildEnabledAccountNames,
  countSignalsByAccount,
  filterSignalsByEnabledAccounts,
} from './latestSignalsFilter';

describe('latest signals account filtering', () => {
  it('keeps only signals for accounts enabled for trading', () => {
    const accounts = [
      {
        account_name: 'ACG-DEMO-2',
        status: 'connected',
        is_active: true,
        is_archived: false,
        pause_trading: false,
      },
      {
        account_name: 'ACG-DEMO-3',
        status: 'connected',
        is_active: true,
        is_archived: false,
      },
      {
        account_name: 'ACG-DEMO',
        status: 'archived',
        is_active: false,
        is_archived: true,
      },
      {
        account_name: 'FTMO - TRAIL - 50K',
        status: 'connected',
        is_active: true,
        selected_for_trading: false,
      },
    ];
    const signals = [
      { id: '1', account_name: 'ACG-DEMO-2' },
      { id: '2', account_name: ' ACG-DEMO-3 ' },
      { id: '3', account_name: 'ACG-DEMO' },
      { id: '4', account_name: 'DEFAULT' },
      { id: '5', account_name: 'FTMO - TRAIL - 50K' },
    ];

    const enabledAccountNames = buildEnabledAccountNames(accounts);
    const visibleSignals = filterSignalsByEnabledAccounts(signals, enabledAccountNames);

    expect(enabledAccountNames).toEqual(['ACG-DEMO-2', 'ACG-DEMO-3']);
    expect(visibleSignals.map((signal) => signal.id)).toEqual(['1', '2']);
    expect(countSignalsByAccount(visibleSignals)).toEqual({
      'ACG-DEMO-2': 1,
      'ACG-DEMO-3': 1,
    });
  });
});
