'use client';

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { useToast } from '@/components/ui/toast';
import {
  cancelAlertBatch,
  createAlertBatch,
  fetchAgentStatus,
  fetchAlertApprovedConfigs,
  fetchAlertBatch,
  fetchAlertBatchEvents,
  fetchAlertBatchResults,
  fetchAlertBatches,
  type AlertBatchCreateApi,
} from '@/lib/api';

export const alertSetupKeys = {
  list: () => ['alert-setup', 'list'] as const,
  detail: (batchId: string) => ['alert-setup', 'detail', batchId] as const,
  results: (batchId: string) => ['alert-setup', 'results', batchId] as const,
  events: (batchId: string) => ['alert-setup', 'events', batchId] as const,
  approved: () => ['alert-setup', 'approved-configs'] as const,
  agent: () => ['alert-setup', 'agent-status'] as const,
};

export function useAlertBatches() {
  return useQuery({
    queryKey: alertSetupKeys.list(),
    queryFn: () => fetchAlertBatches(),
  });
}

export function useAlertBatch(batchId: string | null) {
  return useQuery({
    queryKey: batchId ? alertSetupKeys.detail(batchId) : ['alert-setup', 'detail', 'idle'],
    queryFn: () => fetchAlertBatch(batchId!),
    enabled: Boolean(batchId),
    refetchInterval: (query) =>
      query.state.data?.status === 'running' || query.state.data?.status === 'queued'
        ? 3000
        : false,
  });
}

export function useAlertBatchResults(batchId: string | null) {
  return useQuery({
    queryKey: batchId ? alertSetupKeys.results(batchId) : ['alert-setup', 'results', 'idle'],
    queryFn: () => fetchAlertBatchResults(batchId!),
    enabled: Boolean(batchId),
    refetchInterval: 3000,
  });
}

export function useAlertBatchEvents(batchId: string | null) {
  return useQuery({
    queryKey: batchId ? alertSetupKeys.events(batchId) : ['alert-setup', 'events', 'idle'],
    queryFn: () => fetchAlertBatchEvents(batchId!),
    enabled: Boolean(batchId),
    refetchInterval: 3000,
  });
}

export function useAlertApprovedConfigs() {
  return useQuery({
    queryKey: alertSetupKeys.approved(),
    queryFn: () => fetchAlertApprovedConfigs(),
  });
}

export function useAlertRunnerStatus() {
  return useQuery({
    queryKey: alertSetupKeys.agent(),
    queryFn: fetchAgentStatus,
    refetchInterval: 15_000,
  });
}

export function useCreateAlertBatch() {
  const queryClient = useQueryClient();
  const { addToast } = useToast();
  return useMutation({
    mutationFn: (payload: AlertBatchCreateApi) => createAlertBatch(payload),
    onSuccess: (batch) => {
      queryClient.invalidateQueries({ queryKey: alertSetupKeys.list() });
      queryClient.setQueryData(alertSetupKeys.detail(batch.id), batch);
    },
    onError: (error: Error) => {
      addToast({
        title: 'Start batch failed',
        message: error.message,
        severity: 'critical',
        duration: 8000,
      });
    },
  });
}

export function useCancelAlertBatch() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (batchId: string) => cancelAlertBatch(batchId),
    onSuccess: (batch) => {
      queryClient.invalidateQueries({ queryKey: alertSetupKeys.list() });
      queryClient.setQueryData(alertSetupKeys.detail(batch.id), batch);
      queryClient.invalidateQueries({ queryKey: alertSetupKeys.results(batch.id) });
      queryClient.invalidateQueries({ queryKey: alertSetupKeys.events(batch.id) });
    },
  });
}
