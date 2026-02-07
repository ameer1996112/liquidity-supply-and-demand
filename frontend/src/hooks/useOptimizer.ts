'use client';

import {
  useQuery,
  useMutation,
  useQueryClient,
} from '@tanstack/react-query';
import {
  batchPositionAction,
  fetchHedgeSuggestions,
  generateHedgeSuggestion,
  acceptHedgeSuggestion,
  rejectHedgeSuggestion,
  fetchTrailingStops,
  addTrailingStop,
  removeTrailingStop,
  type HedgeSuggestionApi,
} from '@/lib/api';
import { positionKeys } from './usePositions';

const HEDGE_SUGGESTIONS_KEY = ['portfolio-control', 'optimizer', 'hedge-suggestions'] as const;
const TRAILING_STOPS_KEY = ['portfolio-control', 'optimizer', 'trailing-stops'] as const;

export function useHedgeSuggestions() {
  return useQuery<HedgeSuggestionApi[]>({
    queryKey: HEDGE_SUGGESTIONS_KEY,
    queryFn: fetchHedgeSuggestions,
    staleTime: 15_000,
  });
}

export function useGenerateHedge() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: generateHedgeSuggestion,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: HEDGE_SUGGESTIONS_KEY });
    },
  });
}

export function useAcceptHedge() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (suggestionId: number) => acceptHedgeSuggestion(suggestionId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: HEDGE_SUGGESTIONS_KEY });
      queryClient.invalidateQueries({ queryKey: positionKeys.active });
    },
  });
}

export function useRejectHedge() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (suggestionId: number) => rejectHedgeSuggestion(suggestionId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: HEDGE_SUGGESTIONS_KEY });
    },
  });
}

export function useTrailingStops() {
  return useQuery({
    queryKey: TRAILING_STOPS_KEY,
    queryFn: fetchTrailingStops,
    staleTime: 10_000,
  });
}

export function useAddTrailingStop() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (payload: {
      signal_id: number;
      trail_distance_pips: number;
      activation_price?: number;
      wait_for_breakeven?: boolean;
    }) => addTrailingStop(payload),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: TRAILING_STOPS_KEY });
      queryClient.invalidateQueries({ queryKey: positionKeys.active });
    },
  });
}

export function useRemoveTrailingStop() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (trailingStopId: number) => removeTrailingStop(trailingStopId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: TRAILING_STOPS_KEY });
      queryClient.invalidateQueries({ queryKey: positionKeys.active });
    },
  });
}

export function useBatchPositionAction() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (payload: {
      signal_ids: number[];
      action: 'close' | 'scale_out' | 'move_sl_breakeven' | 'add_trailing';
      action_params?: { trail_distance_pips?: number };
    }) => batchPositionAction(payload),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: positionKeys.active });
      queryClient.invalidateQueries({ queryKey: positionKeys.account });
      queryClient.invalidateQueries({ queryKey: TRAILING_STOPS_KEY });
    },
  });
}
