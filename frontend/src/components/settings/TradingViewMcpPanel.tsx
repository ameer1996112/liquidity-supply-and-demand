'use client';

import { ReactNode, useEffect, useState } from 'react';
import {
  AlertTriangle,
  Check,
  Loader2,
  RefreshCw,
  Shield,
  ShieldAlert,
  ShieldCheck,
} from 'lucide-react';
import {
  fetchLocalChartProviderCompatibility,
  fetchTradingViewMcpConfig,
  patchTradingViewMcpConfig,
  LocalChartProviderCompatibilityResponse,
} from '@/lib/api';
import { cn } from '@/lib/utils';

type LoadState = 'loading' | 'loaded';

function DetailRow({
  label,
  value,
}: {
  label: string;
  value: ReactNode;
}) {
  return (
    <div className='flex items-center justify-between gap-3 border-b border-[var(--to-border)] px-3 py-2 last:border-0'>
      <span className='text-[10px] font-mono uppercase tracking-[0.18em] text-[var(--to-text-dim)]'>
        {label}
      </span>
      <div className='text-right text-xs text-[var(--to-text-secondary)]'>
        {value}
      </div>
    </div>
  );
}

function formatStatusLabel(status?: string): string {
  if (!status) return 'Unavailable';
  return status.replace(/_/g, ' ');
}

function statusTone(status?: string): string {
  if (status === 'supported') {
    return 'bg-[var(--to-long)]/10 text-[var(--to-long)]';
  }
  if (status) {
    return 'bg-amber-500/10 text-amber-300';
  }
  return 'bg-[var(--to-surface-raised)] text-[var(--to-text-dim)]';
}

function chartContextLabel(enabled?: boolean): string {
  if (enabled) return 'Enabled';
  if (enabled === false) return 'Disabled';
  return 'Unknown';
}

function getErrorMessage(error: unknown, fallback: string): string {
  return error instanceof Error ? error.message : fallback;
}

export function TradingViewMcpPanel() {
  const [loadState, setLoadState] = useState<LoadState>('loading');
  const [approvedVersions, setApprovedVersions] = useState<string[]>([]);
  const [compatibility, setCompatibility] =
    useState<LocalChartProviderCompatibilityResponse | null>(null);
  const [backendError, setBackendError] = useState('');
  const [localError, setLocalError] = useState('');
  const [actionError, setActionError] = useState('');
  const [actionMessage, setActionMessage] = useState('');
  const [isSaving, setIsSaving] = useState(false);

  const load = async () => {
    setLoadState('loading');
    setBackendError('');
    setLocalError('');
    setActionError('');

    const [configResult, compatibilityResult] = await Promise.allSettled([
      fetchTradingViewMcpConfig(),
      fetchLocalChartProviderCompatibility(),
    ]);

    if (configResult.status === 'fulfilled') {
      setApprovedVersions(configResult.value.approved_versions);
    } else {
      setApprovedVersions([]);
      setBackendError(
        getErrorMessage(
          configResult.reason,
          'Failed to load approved TradingView versions'
        )
      );
    }

    if (compatibilityResult.status === 'fulfilled') {
      setCompatibility(compatibilityResult.value);
    } else {
      setCompatibility(null);
      setLocalError(
        getErrorMessage(
          compatibilityResult.reason,
          'Failed to reach the local chart provider'
        )
      );
    }

    setLoadState('loaded');
  };

  useEffect(() => {
    void load();
  }, []);

  const localVersion = compatibility?.tradingview_version?.trim() || '';
  const currentVersionApproved =
    localVersion.length > 0 && approvedVersions.includes(localVersion);
  const approveDisabled =
    isSaving || !localVersion || currentVersionApproved || Boolean(backendError);

  const handleApproveCurrentVersion = async () => {
    if (!localVersion || currentVersionApproved) return;

    setIsSaving(true);
    setActionError('');
    setActionMessage('');

    try {
      const mergedVersions = [...new Set([...approvedVersions, localVersion])];
      const response = await patchTradingViewMcpConfig({
        approved_versions: mergedVersions,
      });
      setApprovedVersions(response.approved_versions);
      setActionMessage(`Approved ${localVersion} for local TradingView MCP use.`);

      try {
        const refreshedCompatibility = await fetchLocalChartProviderCompatibility();
        setCompatibility(refreshedCompatibility);
        setLocalError('');
      } catch (error) {
        setLocalError(
          getErrorMessage(
            error,
            'Saved approval, but failed to refresh local compatibility'
          )
        );
      }
    } catch (error) {
      setActionError(
        getErrorMessage(error, 'Failed to approve the current TradingView version')
      );
    } finally {
      setIsSaving(false);
    }
  };

  const statusLabel = formatStatusLabel(compatibility?.status);
  const statusIcon =
    compatibility?.status === 'supported' ? (
      <ShieldCheck className='h-3.5 w-3.5' />
    ) : compatibility?.status ? (
      <ShieldAlert className='h-3.5 w-3.5' />
    ) : (
      <Shield className='h-3.5 w-3.5' />
    );

  return (
    <div className='to-panel' data-testid='tradingview-mcp-panel'>
      <div className='to-panel-header'>
        <div className='flex items-center gap-2'>
          <Shield className='h-3.5 w-3.5 text-text-dim' />
          <span className='panel-label'>TradingView MCP Compatibility</span>
        </div>
        <button
          type='button'
          onClick={() => void load()}
          className='inline-flex items-center gap-1 rounded-md border border-[var(--to-border)] px-2 py-1 text-[10px] font-mono uppercase tracking-[0.18em] text-[var(--to-text-secondary)] transition hover:border-white/15 hover:text-white'
        >
          <RefreshCw className='h-3 w-3' />
          Refresh
        </button>
      </div>

      <div className='space-y-3 p-3'>
        <p className='text-[11px] text-[var(--to-text-dim)]'>
          Approve the detected TradingView Desktop version for local chart
          context. The local provider still reports its live MCP probe result so
          you can see whether the installed version is healthy before or after
          approval.
        </p>

        {backendError && (
          <div className='rounded-lg border border-amber-500/20 bg-amber-500/10 px-3 py-2 text-[11px] text-amber-200'>
            <div className='flex items-center gap-2 font-mono uppercase tracking-[0.18em] text-[10px]'>
              <AlertTriangle className='h-3.5 w-3.5' />
              Backend Config Error
            </div>
            <p className='mt-1 normal-case tracking-normal'>{backendError}</p>
          </div>
        )}

        {localError && (
          <div className='rounded-lg border border-amber-500/20 bg-amber-500/10 px-3 py-2 text-[11px] text-amber-200'>
            <div className='flex items-center gap-2 font-mono uppercase tracking-[0.18em] text-[10px]'>
              <AlertTriangle className='h-3.5 w-3.5' />
              Local Provider Error
            </div>
            <p className='mt-1 normal-case tracking-normal'>{localError}</p>
          </div>
        )}

        {loadState === 'loading' && !compatibility && approvedVersions.length === 0 ? (
          <div className='flex items-center justify-center gap-2 rounded-lg border border-[var(--to-border)] bg-[var(--to-surface-raised)] px-3 py-6 text-[11px] text-[var(--to-text-dim)]'>
            <Loader2 className='h-4 w-4 animate-spin' />
            Loading TradingView MCP status...
          </div>
        ) : (
          <div className='overflow-hidden rounded-lg border border-[var(--to-border)]'>
            <DetailRow
              label='Current Version'
              value={
                <span data-testid='tradingview-mcp-current-version'>
                  {localVersion || 'Unavailable'}
                </span>
              }
            />
            <DetailRow
              label='Local Status'
              value={
                <span
                  data-testid='tradingview-mcp-status'
                  className={cn(
                    'inline-flex items-center gap-1 rounded px-2 py-1 font-mono text-[10px] uppercase tracking-[0.14em]',
                    statusTone(compatibility?.status)
                  )}
                >
                  {statusIcon}
                  {statusLabel}
                </span>
              }
            />
            <DetailRow
              label='Chart Context'
              value={
                <span className='font-mono uppercase tracking-[0.14em] text-[10px]'>
                  {chartContextLabel(compatibility?.chart_context_enabled)}
                </span>
              }
            />
            <DetailRow
              label='Approved Versions'
              value={
                <span className='font-mono text-[11px]'>
                  {approvedVersions.length > 0
                    ? approvedVersions.join(', ')
                    : 'None approved yet'}
                </span>
              }
            />
          </div>
        )}

        {compatibility?.reason && (
          <div className='rounded-lg border border-[var(--to-border)] bg-[var(--to-surface-raised)] px-3 py-2 text-[11px] text-[var(--to-text-dim)]'>
            <span className='font-mono uppercase tracking-[0.18em] text-[10px] text-[var(--to-text-secondary)]'>
              Reason
            </span>
            <p className='mt-1'>{compatibility.reason}</p>
          </div>
        )}

        <div className='flex flex-col gap-2 rounded-lg border border-[var(--to-border)] bg-[var(--to-surface-raised)] px-3 py-3 sm:flex-row sm:items-center sm:justify-between'>
          <div className='text-[11px] text-[var(--to-text-dim)]'>
            {currentVersionApproved ? (
              <span className='inline-flex items-center gap-1 text-[var(--to-long)]'>
                <Check className='h-3.5 w-3.5' />
                Current version already approved.
              </span>
            ) : localVersion ? (
              <span>
                Approve <span className='font-mono text-[var(--to-text-secondary)]'>{localVersion}</span>{' '}
                as a known-good local TradingView version.
              </span>
            ) : (
              <span>Open the local provider to detect a TradingView Desktop version.</span>
            )}
          </div>
          <button
            type='button'
            data-testid='tradingview-mcp-approve-button'
            onClick={() => void handleApproveCurrentVersion()}
            disabled={approveDisabled}
            className='rounded-lg border border-[var(--to-border)] bg-[var(--to-surface-raised)] px-4 py-2 text-[11px] font-mono font-bold uppercase tracking-[0.18em] text-white transition hover:border-white/20 hover:bg-white/5 disabled:cursor-not-allowed disabled:opacity-50'
          >
            {isSaving ? 'Saving…' : currentVersionApproved ? 'Approved' : 'Approve Current Version'}
          </button>
        </div>

        {actionMessage && (
          <p className='text-[11px] text-[var(--to-long)]' data-testid='tradingview-mcp-action-message'>
            {actionMessage}
          </p>
        )}

        {actionError && (
          <p className='text-[11px] text-amber-300' data-testid='tradingview-mcp-action-error'>
            {actionError}
          </p>
        )}
      </div>
    </div>
  );
}
