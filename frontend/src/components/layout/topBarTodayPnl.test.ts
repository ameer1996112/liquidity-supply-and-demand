import { describe, expect, it } from 'vitest';

import { resolveTopBarTodayPnl } from './topBarTodayPnl';

describe('resolveTopBarTodayPnl', () => {
  it('prefers dashboard summary total for global today pnl', () => {
    const value = resolveTopBarTodayPnl({
      selectedAccountName: null,
      activeTradingAccounts: [
        { account_name: 'ACG-DEMO-2', daily_pnl: -144.9 },
        { account_name: 'ACG-DEMO-3', daily_pnl: 0 },
      ],
      summary: {
        total_pnl_today: -444.79,
        total_pnl_all_time: -4446.06,
        total_win_rate: 27.8,
        total_active_positions: 0,
        total_trades_today: 2,
        max_drawdown_pct: 0,
        accounts: [],
      },
      todayPnlFromStats: -144.9,
      riskDailyPnl: -144.9,
    });

    expect(value).toBe(-444.79);
  });

  it('prefers matching dashboard summary account pnl for selected account', () => {
    const value = resolveTopBarTodayPnl({
      selectedAccountName: 'ACG-DEMO-3',
      activeTradingAccounts: [
        { account_name: 'ACG-DEMO-2', daily_pnl: -144.9 },
        { account_name: 'ACG-DEMO-3', daily_pnl: 0 },
      ],
      summary: {
        total_pnl_today: -444.79,
        total_pnl_all_time: -4446.06,
        total_win_rate: 27.8,
        total_active_positions: 0,
        total_trades_today: 2,
        max_drawdown_pct: 0,
        accounts: [
          {
            id: 4,
            name: 'ACG-DEMO-2',
            account_type: 'evaluation',
            run_mode: 'LIVE',
            connection_status: 'connected',
            pnl_today: -143.75,
            pnl_total: -4145.02,
            positions_count: 0,
            win_rate: 28.6,
            trades_today: 1,
          },
          {
            id: 10,
            name: 'ACG-DEMO-3',
            account_type: 'evaluation',
            run_mode: 'LIVE',
            connection_status: 'connected',
            pnl_today: -301.04,
            pnl_total: -301.04,
            positions_count: 0,
            win_rate: 0,
            trades_today: 1,
          },
        ],
      },
      todayPnlFromStats: -144.9,
      riskDailyPnl: -144.9,
    });

    expect(value).toBe(-301.04);
  });
});
