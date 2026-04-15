import { renderToStaticMarkup } from 'react-dom/server';
import { describe, expect, it, vi } from 'vitest';

import RiskMonitorPage from '../page';

vi.mock('@/hooks/useConnectionHealth', () => ({
  useConnectionHealth: () => ({ status: 'healthy' }),
}));

vi.mock('@/components/shared/PageStatusBanner', () => ({
  PageStatusBanner: () => <div>status banner</div>,
}));

vi.mock('@/components/rules/GuardsPanel', () => ({
  GuardsPanel: () => <div>guards panel</div>,
}));

vi.mock('@/components/rules/RiskRulesPanel', () => ({
  RiskRulesPanel: () => <div>risk rules panel</div>,
}));

vi.mock('@/components/rules/StrategyRulesPanel', () => ({
  StrategyRulesPanel: () => <div>strategy panel</div>,
}));

vi.mock('@/hooks/useRiskMonitor', () => ({
  useRiskMonitor: () => ({
    data: {
      summary: {
        total_accounts: 2,
        active_accounts: 2,
        total_equity_usd: 149100,
        total_starting_balance_usd: 150000,
        total_daily_pnl_usd: -700,
        total_open_positions: 3,
        accounts_in_warning: 1,
        accounts_blocked: 0,
        global_kill_switch_active: false,
      },
      accounts: [
        {
          account_name: 'Eval A',
          account_type: 'Evaluation',
          evaluation_phase: 'phase1',
          prop_firm_name: 'FTMO',
          run_mode: 'LIVE',
          connection_status: 'connected',
          starting_balance_usd: 50000,
          current_equity_usd: 49200,
          daily_pnl_usd: -800,
          daily_pnl_pct: -1.6,
          peak_equity_usd: 50000,
          current_drawdown_pct: 1.6,
          max_drawdown_allowed_pct: 8,
          drawdown_utilization_pct: 20,
          daily_loss_used_usd: 800,
          daily_loss_limit_usd: 1000,
          open_positions: 2,
          max_positions: 3,
          trades_today: 2,
          max_trades_today: 2,
          risk_multiplier: 0.5,
          risk_label: 'defensive',
          effective_risk_pct: 0.25,
          base_risk_pct: 0.5,
          kill_switch_active: false,
          blocked: false,
          warning_message: '1 more trade allowed today',
          blocked_reason: null,
          guard_rails: [],
        },
        {
          account_name: 'Eval B',
          account_type: 'Evaluation',
          evaluation_phase: 'phase2',
          prop_firm_name: 'FundedNext',
          run_mode: 'LIVE',
          connection_status: 'connected',
          starting_balance_usd: 100000,
          current_equity_usd: 99900,
          daily_pnl_usd: 100,
          daily_pnl_pct: 0.1,
          peak_equity_usd: 100000,
          current_drawdown_pct: 0.1,
          max_drawdown_allowed_pct: 8,
          drawdown_utilization_pct: 1.25,
          daily_loss_used_usd: 0,
          daily_loss_limit_usd: 2000,
          open_positions: 1,
          max_positions: 3,
          trades_today: 1,
          max_trades_today: 2,
          risk_multiplier: 1,
          risk_label: 'normal',
          effective_risk_pct: 0.5,
          base_risk_pct: 0.5,
          kill_switch_active: false,
          blocked: false,
          warning_message: null,
          blocked_reason: null,
          guard_rails: [],
        },
      ],
      symbol_overrides: [],
      last_updated: '2026-04-16T00:00:00Z',
      data_source: 'test',
    },
    isLoading: false,
    error: null,
  }),
}));

describe('RiskMonitorPage', () => {
  it('renders combined summary and per-account cards', () => {
    const html = renderToStaticMarkup(<RiskMonitorPage />);

    expect(html).toContain('Fleet Summary');
    expect(html).toContain('Eval A');
    expect(html).toContain('Eval B');
  });

  it('does not render the old single-account drawdown label', () => {
    const html = renderToStaticMarkup(<RiskMonitorPage />);

    expect(html).not.toContain('Current DD');
  });
});
