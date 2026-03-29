import { useQuery } from '@tanstack/react-query'
import { apiFetch } from '@/lib/api'
import type { DashboardSummary } from '@/types/trading'

async function fetchDashboardSummary(): Promise<DashboardSummary> {
  return apiFetch<DashboardSummary>('/api/v1/dashboard/summary')
}

export function useDashboardSummary() {
  return useQuery<DashboardSummary>({
    queryKey: ['dashboard-summary'],
    queryFn: fetchDashboardSummary,
    refetchInterval: 30_000,
    staleTime: 15_000,
  })
}
