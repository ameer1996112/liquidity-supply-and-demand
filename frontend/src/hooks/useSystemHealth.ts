'use client';

import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { apiFetch } from '@/lib/api';

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
    queryFn: () =>
      apiFetch<SystemHealth>('/admin/health', {
        signal: AbortSignal.timeout(5000),
      }),
    refetchInterval: 30_000,
    retry: 1,
  });
}

export function useDeadLetters() {
  return useQuery<{ items: DeadLetterItem[]; count: number }>({
    queryKey: adminKeys.deadLetters,
    queryFn: () =>
      apiFetch<{ items: DeadLetterItem[]; count: number }>('/admin/dead-letters', {
        signal: AbortSignal.timeout(5000),
      }),
    refetchInterval: 30_000,
    retry: 1,
  });
}

export function useRetryDeadLetter() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (dlId: string) =>
      apiFetch(`/admin/dead-letters/${dlId}/retry`, { method: 'POST' }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: adminKeys.deadLetters });
      queryClient.invalidateQueries({ queryKey: adminKeys.health });
    },
  });
}

export function useDiscardDeadLetter() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (dlId: string) =>
      apiFetch(`/admin/dead-letters/${dlId}/discard`, { method: 'POST' }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: adminKeys.deadLetters });
      queryClient.invalidateQueries({ queryKey: adminKeys.health });
    },
  });
}

export function useClearDeadLetters() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: () =>
      apiFetch('/admin/dead-letters/clear', { method: 'POST' }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: adminKeys.deadLetters });
      queryClient.invalidateQueries({ queryKey: adminKeys.health });
    },
  });
}
