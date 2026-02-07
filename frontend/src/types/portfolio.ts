/**
 * Portfolio Risk Management Types
 *
 * TypeScript interfaces for portfolio-level risk metrics, VaR analysis,
 * correlation matrices, and sector exposure tracking.
 */

export interface PositionWithRisk {
  symbol: string;
  side: string;
  size: number;
  entry_price: number;
  current_price: number;
  pnl_usd: number;
  notional_value: number;
}

export interface PortfolioRiskDashboard {
  // VaR metrics
  var_95_1d: number;  // 1-day VaR at 95% confidence
  var_99_1d: number;  // 1-day VaR at 99% confidence
  cvar_95: number;  // Conditional VaR (Expected Shortfall)

  // Portfolio metrics
  portfolio_volatility: number;  // Annualized volatility (%)
  total_exposure: number;  // Total notional exposure (USD)
  net_exposure: number;  // Net long/short exposure (USD)
  position_count: number;

  // Correlation metrics
  correlation_avg: number;  // Average pairwise correlation
  max_correlation: number;  // Maximum pairwise correlation

  // VaR limit tracking
  var_limit_usd: number;
  var_utilization_pct: number;

  // Active positions
  positions: PositionWithRisk[];
}

export interface CorrelationMatrix {
  symbols: string[];
  matrix: number[][];  // NxN correlation matrix
}

export interface RiskContribution {
  symbol: string;
  var_contribution_usd: number;
  var_contribution_pct: number;
}

export interface SectorExposure {
  sector: string;
  exposure_usd: number;
  exposure_pct: number;
  limit_pct: number;
  utilization: number;  // 0-100%
  status: 'ok' | 'warning' | 'exceeded';
}

export interface PortfolioSettings {
  portfolio_var_enabled: boolean;
  portfolio_max_var_usd: number;
  portfolio_max_var_pct: number;
  kelly_enabled: boolean;
  kelly_fraction: number;
  correlation_matrix_enabled: boolean;
  max_avg_portfolio_correlation: number;
  sector_limits: {
    forex_majors: number;
    forex_jpy: number;
    forex_eur: number;
    forex_gbp: number;
    indices_us: number;
    indices_eu: number;
    indices_asia: number;
    precious_metals: number;
    commodities: number;
    crypto: number;
  };
}

// Helper type guards
export function isHighRiskStatus(status: SectorExposure['status']): boolean {
  return status === 'warning' || status === 'exceeded';
}

export function getVarUtilizationColor(utilization: number): string {
  if (utilization >= 100) return 'text-red-500';
  if (utilization >= 80) return 'text-yellow-500';
  if (utilization >= 60) return 'text-yellow-400';
  return 'text-green-500';
}

export function getSectorStatusColor(status: SectorExposure['status']): string {
  switch (status) {
    case 'exceeded':
      return 'text-red-500';
    case 'warning':
      return 'text-yellow-500';
    default:
      return 'text-green-500';
  }
}

export function formatVarValue(var_usd: number): string {
  // VaR is typically negative (potential loss)
  const absValue = Math.abs(var_usd);
  if (absValue >= 1000) {
    return `$${(absValue / 1000).toFixed(1)}k`;
  }
  return `$${absValue.toFixed(0)}`;
}
