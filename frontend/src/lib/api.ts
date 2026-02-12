/**
 * API Client Configuration for Railway Deployment
 *
 * Automatically uses Railway backend URL in production,
 * localhost in development.
 */

// Get API base URL from environment or default to localhost
export const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

/**
 * Fetch wrapper with automatic Railway URL handling
 */
export async function apiFetch<T>(
  endpoint: string,
  options?: RequestInit
): Promise<T> {
  const url = `${API_BASE_URL}${endpoint}`;

  const response = await fetch(url, {
    ...options,
    headers: {
      "Content-Type": "application/json",
      ...options?.headers,
    },
  });

  if (!response.ok) {
    const error = await response.text();
    throw new Error(`API Error (${response.status}): ${error}`);
  }

  return response.json();
}

/**
 * Backtest API client
 */
export const backtestAPI = {
  /**
   * Run a backtest
   */
  async runBacktest(request: {
    symbol: string;
    start_date: string;
    end_date: string;
    timeframe: string;
    initial_cash: number;
    commission: number;
    risk_percent: number;
    min_rr_ratio: number;
    require_liquidity_sweep?: boolean;
    reject_compression_arrival?: boolean;
    require_structure_break?: boolean;
  }) {
    return apiFetch<any>("/api/backtest/run", {
      method: "POST",
      body: JSON.stringify(request),
    });
  },

  /**
   * Validate strategy before deploying to live bot
   */
  async validateStrategy(request: {
    symbol: string;
    days_to_test: number;
    timeframe: string;
    risk_percent: number;
    min_rr_ratio: number;
    reject_compression_arrival: boolean;
    min_trades: number;
    min_win_rate: number;
    min_profit_factor: number;
    max_drawdown: number;
  }) {
    return apiFetch<any>("/api/bot/validate-strategy", {
      method: "POST",
      body: JSON.stringify(request),
    });
  },

  /**
   * Health check
   */
  async healthCheck() {
    return apiFetch<{ status: string }>("/api/backtest/health");
  },
};
