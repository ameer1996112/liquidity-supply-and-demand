import { describe, expect, it } from 'vitest';

import { needsCTraderReconnect } from './BrokerProfilesPanel';

describe('needsCTraderReconnect', () => {
  it('shows reconnect for cTrader profiles with expired authorization and a stored token', () => {
    expect(needsCTraderReconnect({
      venue: 'ctrader',
      token_masked: '***RDovaPBw',
      connection_status: 'error',
      connection_error: 'cTrader authorization expired or was revoked. Click Connect cTrader again to authorize this profile.',
    })).toBe(true);
  });

  it('keeps connected cTrader profiles on the normal test flow', () => {
    expect(needsCTraderReconnect({
      venue: 'ctrader',
      token_masked: '***RDovaPBw',
      connection_status: 'connected',
      connection_error: null,
    })).toBe(false);
  });
});
