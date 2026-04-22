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
  value_type: 'bool' | 'int' | 'float' | 'str';
  current_value: number | boolean | string;
  default: number | boolean | string;
  min_value: number | null;
  max_value: number | null;
  unit: string;
}

export interface DynamicThresholdInfo {
  enabled: boolean;
  base: number;
  min_val: number;
  max_val: number;
  description: string;
}

export interface GuardConfig {
  guard_id: string;
  name: string;
  description: string;
  user_description: string;
  tier: 'critical' | 'important' | 'convenience';
  group: string;
  group_label: string;
  value_type: 'bool' | 'int' | 'float' | 'str';
  enabled: boolean | number;
  default: boolean | number;
  min_value: number | null;
  max_value: number | null;
  unit: string;
  thresholds: ThresholdConfig[];
  rejection_count_7d: number;
  last_rejection_reason: string | null;
  dynamic_threshold: DynamicThresholdInfo | null;
  scope?: 'global' | 'account' | 'mixed';
}

export interface GuardsConfigResponse {
  groups: Record<string, GuardConfig[]>;
  group_labels: Record<string, string>;
  tier_labels: Record<string, string>;
  total_rejections_7d: number;
  total_signals_7d: number;
}

export interface GuardAccount {
  id: string;
  name: string;
  run_mode: string;
}

export interface GuardAccountsResponse {
  accounts: GuardAccount[];
}

export interface GuardUpdateRequest {
  value: boolean | number | string;
  thresholds?: Record<string, boolean | number | string>;
  change_reason: string;
}

export interface GuardUpdateResponse {
  guard_id: string;
  setting_key: string;
  old_value: boolean | number | string;
  new_value: boolean | number | string;
  confirmed_value: boolean | number | string;
  threshold_updates: Record<string, boolean | number | string>;
}

export interface RejectionEntry {
  guard_name: string;
  symbol: string;
  reason: string;
  timestamp: string;
}

// ── API Functions ──────────────────────────────────────

async function fetchGlobalGuardsConfig(): Promise<GuardsConfigResponse> {
  return apiFetch<GuardsConfigResponse>('/api/v1/guards/config');
}

async function updateGlobalGuard(
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

async function fetchGuardAccounts(): Promise<GuardAccountsResponse> {
  return apiFetch<GuardAccountsResponse>('/api/v1/guards/accounts');
}

async function fetchAccountGuardsConfig(accountId: string): Promise<GuardsConfigResponse> {
  return apiFetch<GuardsConfigResponse>(`/api/v1/guards/config/account/${accountId}`);
}

async function updateAccountGuard(
  accountId: string,
  guardId: string,
  body: GuardUpdateRequest
): Promise<GuardUpdateResponse> {
  return apiFetch<GuardUpdateResponse>(`/api/v1/guards/config/account/${accountId}/${guardId}`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });
}

// ── Hooks ──────────────────────────────────────────────

const GLOBAL_GUARDS_CONFIG_KEY = ['guards', 'global'] as const;
const GUARD_ACCOUNTS_KEY = ['guards', 'accounts'] as const;
const GUARDS_REJECTIONS_KEY = ['guards', 'rejections'] as const;

export function useGlobalGuardsConfig() {
  return useQuery({
    queryKey: GLOBAL_GUARDS_CONFIG_KEY,
    queryFn: fetchGlobalGuardsConfig,
    staleTime: 30_000,
    refetchInterval: 60_000,
  });
}

export function useGuardAccounts() {
  return useQuery({
    queryKey: GUARD_ACCOUNTS_KEY,
    queryFn: fetchGuardAccounts,
    staleTime: 30_000,
    refetchInterval: 60_000,
  });
}

export function useAccountGuardsConfig(accountId: string | null) {
  return useQuery({
    queryKey: ['guards', 'account', accountId],
    queryFn: () => fetchAccountGuardsConfig(accountId as string),
    enabled: Boolean(accountId),
    staleTime: 30_000,
    refetchInterval: 60_000,
  });
}

export function useUpdateGlobalGuard() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({
      guardId,
      ...body
    }: GuardUpdateRequest & { guardId: string }) =>
      updateGlobalGuard(guardId, body),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: GLOBAL_GUARDS_CONFIG_KEY });
    },
  });
}

export function useUpdateAccountGuard() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({
      accountId,
      guardId,
      ...body
    }: GuardUpdateRequest & { accountId: string; guardId: string }) =>
      updateAccountGuard(accountId, guardId, body),
    onSuccess: (_result, variables) => {
      queryClient.invalidateQueries({ queryKey: ['guards', 'account', variables.accountId] });
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
