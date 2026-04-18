'use client';

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import {
  cancelOptimizerRun,
  createOptimizerRun,
  fetchAgentStatus,
  fetchOptimizerRun,
  fetchOptimizerRunEvents,
  fetchOptimizerRunResults,
  fetchOptimizerRunStressResults,
  fetchOptimizerRunTrials,
  fetchOptimizerRuns,
  type OptimizerRunCreateApi,
} from '@/lib/api';

export const optimizerRunKeys = {
  list: () => ['optimizer-runs', 'list'] as const,
  detail: (runId: string) => ['optimizer-runs', 'detail', runId] as const,
  results: (runId: string) => ['optimizer-runs', 'results', runId] as const,
  events: (runId: string) => ['optimizer-runs', 'events', runId] as const,
  trials: (runId: string) => ['optimizer-runs', 'trials', runId] as const,
  trialSymbol: (runId: string, symbol: string) => ['optimizer-runs', 'trials', runId, symbol] as const,
  stressResults: (runId: string) => ['optimizer-runs', 'stress-results', runId] as const,
  stressResultSymbol: (runId: string, symbol: string) =>
    ['optimizer-runs', 'stress-results', runId, symbol] as const,
};

export function useOptimizerRuns() {
  return useQuery({
    queryKey: optimizerRunKeys.list(),
    queryFn: () => fetchOptimizerRuns(),
  });
}

export function useOptimizerRun(runId: string | null) {
  return useQuery({
    queryKey: runId ? optimizerRunKeys.detail(runId) : ['optimizer-runs', 'detail', 'idle'],
    queryFn: () => fetchOptimizerRun(runId!),
    enabled: Boolean(runId),
    refetchInterval: (query) =>
      query.state.data?.status === 'running' || query.state.data?.status === 'queued'
        ? 3000
        : false,
  });
}

export function useOptimizerRunResults(runId: string | null) {
  return useQuery({
    queryKey: runId ? optimizerRunKeys.results(runId) : ['optimizer-runs', 'results', 'idle'],
    queryFn: () => fetchOptimizerRunResults(runId!),
    enabled: Boolean(runId),
    refetchInterval: 3000,
  });
}

export function useOptimizerRunEvents(runId: string | null) {
  return useQuery({
    queryKey: runId ? optimizerRunKeys.events(runId) : ['optimizer-runs', 'events', 'idle'],
    queryFn: () => fetchOptimizerRunEvents(runId!),
    enabled: Boolean(runId),
    refetchInterval: 3000,
  });
}

export function useOptimizerRunTrials(runId: string | null, symbol?: string | null) {
  return useQuery({
    queryKey: runId
      ? symbol
        ? optimizerRunKeys.trialSymbol(runId, symbol)
        : optimizerRunKeys.trials(runId)
      : ['optimizer-runs', 'trials', 'idle'],
    queryFn: () => fetchOptimizerRunTrials(runId!, symbol ?? undefined),
    enabled: Boolean(runId),
    refetchInterval: 3000,
  });
}

export function useOptimizerRunStressResults(runId: string | null, symbol?: string | null) {
  return useQuery({
    queryKey: runId
      ? symbol
        ? optimizerRunKeys.stressResultSymbol(runId, symbol)
        : optimizerRunKeys.stressResults(runId)
      : ['optimizer-runs', 'stress-results', 'idle'],
    queryFn: () => fetchOptimizerRunStressResults(runId!, symbol ?? undefined),
    enabled: Boolean(runId),
    refetchInterval: 5000,
  });
}

export function useCreateOptimizerRun() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (payload: OptimizerRunCreateApi) => createOptimizerRun(payload),
    onSuccess: (run) => {
      queryClient.invalidateQueries({ queryKey: optimizerRunKeys.list() });
      queryClient.setQueryData(optimizerRunKeys.detail(run.id), run);
    },
  });
}

export function useAgentStatus() {
  return useQuery({
    queryKey: ['optimizer', 'agent-status'] as const,
    queryFn: fetchAgentStatus,
    refetchInterval: 15_000,
  });
}

export function useCancelOptimizerRun() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (runId: string) => cancelOptimizerRun(runId),
    onSuccess: (run) => {
      queryClient.invalidateQueries({ queryKey: optimizerRunKeys.list() });
      queryClient.setQueryData(optimizerRunKeys.detail(run.id), run);
      queryClient.invalidateQueries({ queryKey: optimizerRunKeys.results(run.id) });
      queryClient.invalidateQueries({ queryKey: optimizerRunKeys.events(run.id) });
      queryClient.invalidateQueries({ queryKey: optimizerRunKeys.trials(run.id) });
      queryClient.invalidateQueries({ queryKey: optimizerRunKeys.stressResults(run.id) });
    },
  });
}
