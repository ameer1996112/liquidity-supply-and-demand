import { useQuery } from '@tanstack/react-query';
import { getApiUrl } from '@/lib/api';

type HealthStatus = 'healthy' | 'degraded' | 'offline';

interface HealthResult {
  status: HealthStatus;
  isConnected: boolean;
}

/**
 * Polls /health and returns connection status.
 * Shared between TopBar and Dashboard — both use the same query key
 * so TanStack Query deduplicates the network request automatically.
 */
export function useConnectionHealth(refetchInterval = 30_000): HealthResult {
  const { data } = useQuery({
    queryKey: ['connection-health'],
    queryFn: async (): Promise<{ status: HealthStatus }> => {
      const base = getApiUrl();
      if (!base) return { status: 'offline' };
      try {
        const res = await fetch(`${base}/health`, {
          signal: AbortSignal.timeout(3_000),
        });
        if (!res.ok) return { status: 'offline' };
        return res.json();
      } catch {
        return { status: 'offline' };
      }
    },
    refetchInterval,
    staleTime: refetchInterval / 2,
  });

  const status = data?.status ?? 'offline';
  return { status, isConnected: status !== 'offline' };
}
