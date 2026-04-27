'use client';

import { createContext, useContext, type ReactNode } from 'react';
import { useQuery } from '@tanstack/react-query';

import { apiFetch } from '@/lib/api';

interface ActiveBrokerProfile {
  id: number;
  name: string;
  is_active: boolean;
  selected_for_trading: boolean;
  run_mode: string;
  account_type: 'personal' | 'evaluation' | 'funded';
  prop_firm_name?: string | null;
}

interface ActiveAccountContextValue {
  activeProfile: ActiveBrokerProfile | null;
  broker_profile_id: number | null;
  isLoading: boolean;
}

const ActiveAccountContext = createContext<ActiveAccountContextValue>({
  activeProfile: null,
  broker_profile_id: null,
  isLoading: true,
});

async function fetchBrokerProfiles(): Promise<ActiveBrokerProfile[]> {
  return apiFetch<ActiveBrokerProfile[]>('/api/broker-profiles');
}

export function ActiveAccountProvider({ children }: { children: ReactNode }) {
  const { data: profiles, isLoading } = useQuery({
    queryKey: ['broker-profiles'],
    queryFn: fetchBrokerProfiles,
    refetchInterval: 30_000,
    staleTime: 20_000,
  });

  const activeProfile =
    profiles?.find((p) => p.is_active !== false && p.selected_for_trading) ?? null;

  return (
    <ActiveAccountContext.Provider
      value={{
        activeProfile,
        broker_profile_id: activeProfile?.id ?? null,
        isLoading,
      }}
    >
      {children}
    </ActiveAccountContext.Provider>
  );
}

export function useActiveAccount(): ActiveAccountContextValue {
  return useContext(ActiveAccountContext);
}
