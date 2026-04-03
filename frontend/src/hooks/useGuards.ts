'use client';

import {
  useQuery,
  useMutation,
  useQueryClient,
} from '@tanstack/react-query';
import { apiFetch } from '@/lib/api';

// ── Types ──────────────────────────────────────────────

export interface ThresholdConfig {
  setting_key: string;
  name: string;
  value_type: 'bool' | 'int' | 'float';
  current_value: number | boolean;
  default: number | boolean;
  min_value: number | null;
  max_value: number | null;
  unit: string;
}

export interface GuardConfig {
  guard_id: string;
  name: string;
  description: string;
  user_description: string;
  tier: 'critical' | 'important' | 'convenience';
  group: string;
  group_label: string;
  value_type: 'bool' | 'int' | 'float';
  enabled: boolean | number;
  default: boolean | number;
  min_value: number | null;
  max_value: number | null;
  unit: string;
  thresholds: ThresholdConfig[];
  rejection_count_7d: number;
  last_rejection_reason: string | null;
}

export interface GuardsConfigResponse {
  groups: Record<string, GuardConfig[]>;
  group_labels: Record<string, string>;
  tier_labels: Record<string, string>;
  total_rejections_7d: number;
  total_signals_7d: number;
}

export interface GuardUpdateRequest {
  value: boolean | number;
  thresholds?: Record<string, boolean | number>;
  change_reason: string;
}

export interface GuardUpdateResponse {
  guard_id: string;
  setting_key: string;
  old_value: boolean | number;
  new_value: boolean | number;
  confirmed_value: boolean | number;
  threshold_updates: Record<string, boolean | number>;
}

export interface RejectionEntry {
  guard_name: string;
  symbol: string;
  reason: string;
  timestamp: string;
}

// ── API Functions ──────────────────────────────────────

async function fetchGuardsConfig(): Promise<GuardsConfigResponse> {
  return apiFetch<GuardsConfigResponse>('/api/v1/guards/config');
}

async function updateGuard(
  guardId: string,
  body: GuardUpdateRequest
): Promise<GuardUpdateResponse> {
  return apiFetch<GuardUpdateResponse>(`/api/v1/guards/config/${guardId}`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });
}

async function fetchRejections(days = 7): Promise<RejectionEntry[]> {
  return apiFetch<RejectionEntry[]>(
    `/api/v1/guards/rejections?days=${days}&limit=50`
  );
}

// ── Hooks ──────────────────────────────────────────────

const GUARDS_CONFIG_KEY = ['guards', 'config'] as const;
const GUARDS_REJECTIONS_KEY = ['guards', 'rejections'] as const;

export function useGuardsConfig() {
  return useQuery({
    queryKey: GUARDS_CONFIG_KEY,
    queryFn: fetchGuardsConfig,
    staleTime: 30_000,
    refetchInterval: 60_000,
  });
}

export function useUpdateGuard() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({
      guardId,
      ...body
    }: GuardUpdateRequest & { guardId: string }) =>
      updateGuard(guardId, body),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: GUARDS_CONFIG_KEY });
    },
  });
}

export function useGuardRejections(days = 7) {
  return useQuery({
    queryKey: [...GUARDS_REJECTIONS_KEY, days],
    queryFn: () => fetchRejections(days),
    staleTime: 60_000,
    refetchInterval: 120_000,
  });
}
