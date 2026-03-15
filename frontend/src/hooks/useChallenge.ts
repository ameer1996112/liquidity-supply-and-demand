'use client';

import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import {
  fetchChallengeSettings,
  updateChallengeSettings,
  type ChallengeSettings,
} from '@/lib/api';

export function useChallengeSettings(accountName: string) {
  return useQuery({
    queryKey: ['challenge-settings', accountName],
    queryFn: () => fetchChallengeSettings(accountName),
    staleTime: 30_000,
    enabled: !!accountName,
  });
}

export function useUpdateChallengeSettings(accountName: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (settings: Omit<ChallengeSettings, 'account_name' | 'broker_profile_id' | 'evaluation_start_date'>) =>
      updateChallengeSettings(accountName, settings),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['challenge-settings', accountName] });
      queryClient.invalidateQueries({ queryKey: ['account-detail', accountName] });
    },
  });
}
