import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { apiFetch } from '@/lib/api';

export interface FirmInfo {
  firm_id: string;
  firm_display_name: string;
  challenge_type?: string;
  max_daily_loss_pct?: number;
  max_drawdown_pct?: number;
  profit_target_pct?: number;
  min_trading_days?: number;
  max_trading_days?: number;
}

export interface ChallengeStatusResponse {
  status: string;
  firm_detected: boolean;
  firm_info?: FirmInfo;
  metrics?: any;
}

export function usePropFirmChallenge(accountName: string | undefined) {
  const queryClient = useQueryClient();

  const query = useQuery<ChallengeStatusResponse>({
    queryKey: ['prop-firm-challenge', accountName],
    queryFn: async () => {
      if (!accountName) return null as any;
      return apiFetch(`/api/v1/prop-firm/challenge-status/${accountName}`);
    },
    enabled: !!accountName,
    refetchInterval: 10000, // Poll every 10 seconds
  });

  const updateConfig = useMutation({
    mutationFn: async (config: { challenge_type: string }) => {
      return apiFetch(`/api/v1/prop-firm/challenge-config/${accountName}`, {
        method: 'PATCH',
        body: JSON.stringify(config),
      });
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['prop-firm-challenge', accountName] });
    },
  });

  return {
    ...query,
    updateConfig,
  };
}
