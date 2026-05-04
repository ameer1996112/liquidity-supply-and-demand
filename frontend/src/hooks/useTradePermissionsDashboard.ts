import { useQuery } from '@tanstack/react-query'
import { apiFetch } from '@/lib/api'

export type TradeDecision =
  | 'TRADE_NORMAL_RISK'
  | 'TRADE_REDUCED_RISK'
  | 'WATCH_ONLY'
  | 'NO_TRADE'

export interface DailyPermission {
  status: TradeDecision
  risk_per_trade_pct: number
  max_trades_today: number
  session_utc?: {
    start: number
    end: number
  }
  expires_at?: string
  reasons?: string[]
}

export interface TradePermissionsDashboard {
  global_decision: TradeDecision
  allowed_today: Record<string, DailyPermission>
  blocked_today: Record<string, string[]>
  watch_only: Record<string, string[]>
  research_approved_candidates: Record<string, unknown>
  expiring_candidates: unknown[]
  recent_rejects: unknown[]
  issue_detector: { status?: string }
  execution_health: { status?: string }
  account_risk_buffer: { status?: string }
}

async function fetchTradePermissionsDashboard(): Promise<TradePermissionsDashboard> {
  return apiFetch<TradePermissionsDashboard>('/api/v1/dashboard/trade-permissions')
}

export function useTradePermissionsDashboard() {
  return useQuery<TradePermissionsDashboard>({
    queryKey: ['trade-permissions-dashboard'],
    queryFn: fetchTradePermissionsDashboard,
    refetchInterval: 30_000,
    staleTime: 15_000,
  })
}
