'use client';

import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { getApiUrl } from '@/lib/api';

export interface DeadLetterItem {
  id: string;
  payload: Record<string, unknown>;
  error: string;
  attempt: number;
  failed_at: number;
}

export interface SystemHealth {
  dead_letter_count: number;
  queue_depth: number;
  redis_connected: boolean;
}

export const adminKeys = {
  health: ['admin-health'] as const,
  deadLetters: ['admin-dead-letters'] as const,
};

export function useSystemHealth() {
  return useQuery<SystemHealth>({
    queryKey: adminKeys.health,
    queryFn: async () => {
      const base = getApiUrl();
      if (!base) throw new Error('API URL not configured');
      const res = await fetch(`${base}/admin/health`, {
        signal: AbortSignal.timeout(5000),
      });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      return res.json();
    },
    refetchInterval: 30_000,
    retry: 1,
  });
}

export function useDeadLetters() {
  return useQuery<{ items: DeadLetterItem[]; count: number }>({
    queryKey: adminKeys.deadLetters,
    queryFn: async () => {
      const base = getApiUrl();
      if (!base) throw new Error('API URL not configured');
      const res = await fetch(`${base}/admin/dead-letters`, {
        signal: AbortSignal.timeout(5000),
      });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      return res.json();
    },
    refetchInterval: 30_000,
    retry: 1,
  });
}

export function useRetryDeadLetter() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (dlId: string) => {
      const base = getApiUrl();
      if (!base) throw new Error('API URL not configured');
      const res = await fetch(`${base}/admin/dead-letters/${dlId}/retry`, {
        method: 'POST',
      });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      return res.json();
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: adminKeys.deadLetters });
      queryClient.invalidateQueries({ queryKey: adminKeys.health });
    },
  });
}

export function useDiscardDeadLetter() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (dlId: string) => {
      const base = getApiUrl();
      if (!base) throw new Error('API URL not configured');
      const res = await fetch(`${base}/admin/dead-letters/${dlId}/discard`, {
        method: 'POST',
      });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      return res.json();
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: adminKeys.deadLetters });
      queryClient.invalidateQueries({ queryKey: adminKeys.health });
    },
  });
}

export function useClearDeadLetters() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async () => {
      const base = getApiUrl();
      if (!base) throw new Error('API URL not configured');
      const res = await fetch(`${base}/admin/dead-letters/clear`, {
        method: 'POST',
      });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      return res.json();
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: adminKeys.deadLetters });
      queryClient.invalidateQueries({ queryKey: adminKeys.health });
    },
  });
}
