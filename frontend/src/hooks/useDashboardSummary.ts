import { useQuery } from '@tanstack/react-query'
import type { DashboardSummary } from '@/types/trading'

async function fetchDashboardSummary(): Promise<DashboardSummary> {
  const res = await fetch('/api/v1/dashboard/summary')
  if (!res.ok) throw new Error('Failed to fetch dashboard summary')
  return res.json()
}

export function useDashboardSummary() {
  return useQuery<DashboardSummary>({
    queryKey: ['dashboard-summary'],
    queryFn: fetchDashboardSummary,
    refetchInterval: 30_000,
    staleTime: 15_000,
  })
}
