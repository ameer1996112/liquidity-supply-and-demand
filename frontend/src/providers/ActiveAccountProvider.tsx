'use client';

import { createContext, useContext, type ReactNode } from 'react';
import { useQuery } from '@tanstack/react-query';

const API_BASE = (process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000').replace(/\/$/, '');

interface ActiveBrokerProfile {
  id: number;
  name: string;
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
  const r = await fetch(`${API_BASE}/api/broker-profiles`);
  if (!r.ok) throw new Error('Failed to load broker profiles');
  return r.json();
}

export function ActiveAccountProvider({ children }: { children: ReactNode }) {
  const { data: profiles, isLoading } = useQuery({
    queryKey: ['broker-profiles'],
    queryFn: fetchBrokerProfiles,
    refetchInterval: 30_000,
    staleTime: 20_000,
  });

  const activeProfile = profiles?.find((p) => p.selected_for_trading) ?? null;

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
