'use client';

import { useEffect, useState } from 'react';
import {
  AiConfigResponse,
  AiOperatingLayerConfigResponse,
  fetchAiConfig,
  fetchAiOperatingLayerConfig,
  fetchGraduationStatus,
  fetchAiModeToggles,
  fetchKillSwitchLog,
  patchAiOperatingLayerConfig,
  setAiMode,
  GraduationReadiness,
  KillSwitchLogEntry,
} from '@/lib/api';
import { cn } from '@/lib/utils';
import {
  Brain,
  Shield,
  Zap,
  Target,
  AlertTriangle,
  RefreshCw,
  Check,
  X,
  Loader2,
  GraduationCap,
  History,
  Save,
} from 'lucide-react';

type LoadState = 'loading' | 'loaded' | 'error';

function StatusBadge({ enabled, label }: { enabled: boolean; label?: string }) {
  return (
    <span
      className={cn(
        'inline-flex items-center gap-1 font-mono text-[10px] px-1.5 py-0.5 rounded',
        enabled ? 'text-[var(--to-long)] bg-[var(--to-long)]/10' : 'text-[var(--to-text-dim)] bg-[var(--to-surface-raised)]/30'
      )}
    >
      {enabled ? <Check className="w-3 h-3" /> : <X className="w-3 h-3" />}
      {label || (enabled ? 'ON' : 'OFF')}
    </span>
  );
}

function ConfigRow({
  label,
  value,
  valueClass,
}: {
  label: string;
  value: React.ReactNode;
  valueClass?: string;
}) {
  return (
    <div className="flex items-center justify-between py-2">
      <span className="text-[11px] text-[var(--to-text-dim)] uppercase tracking-wider font-mono">{label}</span>
      <span className={cn('font-mono text-xs text-[var(--to-text-secondary)]', valueClass)}>{value}</span>
    </div>
  );
}

function SectionCard({
  title,
  icon,
  children,
}: {
  title: string;
  icon: React.ReactNode;
  children: React.ReactNode;
}) {
  return (
    <div className="to-panel">
      <div className="to-panel-header">
        <div className="flex items-center gap-2">
          <div className="text-text-dim">{icon}</div>
          <span className="font-mono text-[11px] text-text-muted uppercase tracking-[0.18em]">
            {title}
          </span>
        </div>
      </div>
      <div className="px-4 py-2 divide-y divide-panel-border-subtle">{children}</div>
    </div>
  );
}

export function AiConfigPanel() {
  const [config, setConfig] = useState<AiConfigResponse | null>(null);
  const [aiOperatingLayerConfig, setAiOperatingLayerConfig] =
    useState<AiOperatingLayerConfigResponse | null>(null);
  const [draftAiOperatingLayerModules, setDraftAiOperatingLayerModules] =
    useState<Record<string, 'inherit' | 'enabled' | 'disabled'>>({});
  const [draftAiOperatingLayerProvider, setDraftAiOperatingLayerProvider] =
    useState<AiOperatingLayerConfigResponse['provider'] | null>(null);
  const [graduation, setGraduation] = useState<GraduationReadiness | null>(null);
  const [state, setState] = useState<LoadState>('loading');
  const [error, setError] = useState('');
  const [modeChanging, setModeChanging] = useState(false);
  const [aiOperatingLayerSaving, setAiOperatingLayerSaving] = useState(false);
  const [showEnforceConfirm, setShowEnforceConfirm] = useState(false);
  const [toggles, setToggles] = useState<Array<{ from_mode: string; to_mode: string; reason: string | null; created_at: string }>>([]);
  const [showToggles, setShowToggles] = useState(false);
  const [killEvents, setKillEvents] = useState<KillSwitchLogEntry[]>([]);
  const [showKillEvents, setShowKillEvents] = useState(false);

  const load = () => {
    setState('loading');
    setError('');
    Promise.all([
      fetchAiConfig(),
      fetchGraduationStatus(),
      fetchAiOperatingLayerConfig(),
    ])
      .then(([data, grad, aiLayer]) => {
        setConfig(data);
        setGraduation(grad);
        setAiOperatingLayerConfig(aiLayer);
        setDraftAiOperatingLayerModules(aiLayer.modules || {});
        setDraftAiOperatingLayerProvider(aiLayer.provider);
        setState('loaded');
      })
      .catch((err) => {
        setError(err instanceof Error ? err.message : 'Failed to load');
        setState('error');
      });
  };

  const handleSetEnforce = async () => {
    if (!graduation?.ready) return;
    setModeChanging(true);
    try {
      await setAiMode('enforce', 'graduation_ready');
      setShowEnforceConfirm(false);
      load();
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to set enforce');
    } finally {
      setModeChanging(false);
    }
  };

  const loadToggles = () => {
    fetchAiModeToggles(20)
      .then((r) => setToggles(r.toggles || []))
      .catch(() => setToggles([]));
  };

  const loadKillLog = () => {
    fetchKillSwitchLog(20)
      .then((r) => setKillEvents(r.events || []))
      .catch(() => setKillEvents([]));
  };

  const handleSetShadow = async () => {
    setModeChanging(true);
    try {
      await setAiMode('shadow', 'manual');
      load();
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to set shadow');
    } finally {
      setModeChanging(false);
    }
  };

  const handleSaveAiOperatingLayer = async () => {
    if (!aiOperatingLayerConfig) return;
    setAiOperatingLayerSaving(true);
    try {
      const next = await patchAiOperatingLayerConfig({
        panic_mode: aiOperatingLayerConfig.panic_mode,
        modules: draftAiOperatingLayerModules,
        provider: draftAiOperatingLayerProvider || undefined,
      });
      setAiOperatingLayerConfig(next);
      setDraftAiOperatingLayerModules(next.modules || {});
      setDraftAiOperatingLayerProvider(next.provider);
    } catch (e) {
      setError(
        e instanceof Error
          ? e.message
          : 'Failed to save AI Operating Layer config'
      );
    } finally {
      setAiOperatingLayerSaving(false);
    }
  };

  useEffect(() => {
    load();
  }, []);

  if (state === 'loading') {
    return (
      <div className="to-panel p-8 flex items-center justify-center">
        <Loader2 className="w-5 h-5 text-text-muted animate-spin" />
        <span className="ml-2 text-sm text-text-muted font-mono">
          Loading AI configuration...
        </span>
      </div>
    );
  }

  if (state === 'error') {
    return (
      <div className="to-panel p-6 flex flex-col items-center justify-center gap-3">
        <AlertTriangle className="w-8 h-8 text-amber-400" />
        <span className="text-sm text-text-secondary font-mono">{error}</span>
        <p className="text-[11px] text-text-muted text-center max-w-md">
          Cannot reach backend API. Make sure NEXT_PUBLIC_API_URL is set and the Railway
          backend is running. AI/ML settings are configured via Railway environment
          variables.
        </p>
        <button
          onClick={load}
          className="flex items-center gap-1.5 px-3 py-1.5 rounded text-xs font-mono bg-surface-raised text-text-secondary hover:bg-surface-raised/90 transition-colors"
        >
          <RefreshCw className="w-3 h-3" />
          Retry
        </button>
      </div>
    );
  }

  if (!config) return null;

  const { ai, ml, ensemble, execution, risk } = config;
  const moduleEntries = Object.entries(draftAiOperatingLayerModules || {});

  return (
    <div className="space-y-4">
      {/* Header with refresh */}
      <div className="flex items-center justify-between">
        <span className="font-mono text-[11px] text-text-muted uppercase tracking-[0.18em]">
          Live Configuration from Railway
        </span>
        <button
          onClick={load}
          className="flex items-center gap-1.5 text-[10px] font-mono text-text-muted hover:text-text-secondary transition-colors"
        >
          <RefreshCw className="w-3 h-3" />
          Refresh
        </button>
      </div>

      {/* AI Guardian */}
      <SectionCard title="AI Guardian (LLM)" icon={<Brain className="w-4 h-4" />}>
        <ConfigRow label="Status" value={<StatusBadge enabled={ai.ai_filter_enabled} />} />
        <ConfigRow label="Provider" value={ai.ai_provider?.toUpperCase()} />
        <ConfigRow label="Model" value={ai.ai_model} />
        <ConfigRow label="Base URL" value={ai.ai_base_url} />
        <ConfigRow label="Min Confidence" value={`${ai.ai_min_confidence}%`} />
        <ConfigRow label="Timeout" value={`${ai.ai_timeout_seconds}s`} />
        <ConfigRow
          label="API Key"
          value={ai.ai_api_key_set ? 'Configured' : 'Not set'}
          valueClass={ai.ai_api_key_set ? 'text-[var(--to-long)]' : 'text-rose-400'}
        />
      </SectionCard>

      {/* ML Guardian */}
      <SectionCard title="ML Guardian (Random Forest)" icon={<Shield className="w-4 h-4" />}>
        <ConfigRow label="Status" value={<StatusBadge enabled={ml.ml_guardian_enabled} />} />
        <ConfigRow label="Min Win Probability" value={`${(ml.ml_min_confidence * 100).toFixed(0)}%`} />
        <ConfigRow label="Model" value="RandomForest (200 trees, depth=10)" />
      </SectionCard>

      {/* Ensemble Brain */}
      <SectionCard title="Ensemble Brain" icon={<Zap className="w-4 h-4" />}>
        <ConfigRow label="LLM Filter" value={<StatusBadge enabled={ensemble.enable_llm_filter} />} />
        <ConfigRow label="Shadow Mode" value={<StatusBadge enabled={ensemble.run_shadow_mode} label={ensemble.run_shadow_mode ? 'SHADOW' : 'LIVE'} />} />
        <ConfigRow label="RAG Engine" value="Supabase pgvector" />
        <ConfigRow label="Embeddings" value="text-embedding-3-small" />
        <ConfigRow label="RAG Top-K" value="4 rules" />
      </SectionCard>

      {/* Sprint 3.4: Strategy Graduation */}
      <SectionCard title="Strategy Graduation" icon={<GraduationCap className="w-4 h-4" />}>
        <ConfigRow
          label="AI Mode"
          value={
            <div className="flex items-center gap-2">
              <StatusBadge
                enabled={ensemble.ai_mode === 'enforce'}
                label={ensemble.ai_mode === 'enforce' ? 'ENFORCE' : 'SHADOW'}
              />
              {ensemble.ai_mode === 'shadow' && graduation?.ready && (
                <>
                  {!showEnforceConfirm ? (
                    <button
                      onClick={() => setShowEnforceConfirm(true)}
                      disabled={modeChanging}
                      className="text-[10px] px-2 py-0.5 rounded bg-[var(--to-long)]/20 text-[var(--to-long)] hover:bg-emerald-500/30 font-mono"
                    >
                      Enable Enforce
                    </button>
                  ) : (
                    <div className="flex items-center gap-1">
                      <button
                        onClick={handleSetEnforce}
                        disabled={modeChanging}
                        className="text-[10px] px-2 py-0.5 rounded bg-emerald-500/30 text-[var(--to-long)] font-mono"
                      >
                        {modeChanging ? '…' : 'Confirm'}
                      </button>
                      <button
                        onClick={() => setShowEnforceConfirm(false)}
                        disabled={modeChanging}
                        className="text-[10px] px-2 py-0.5 rounded bg-[var(--to-surface-raised)] text-[var(--to-text-secondary)] font-mono"
                      >
                        Cancel
                      </button>
                    </div>
                  )}
                </>
              )}
              {ensemble.ai_mode === 'enforce' && (
                <button
                  onClick={handleSetShadow}
                  disabled={modeChanging}
                  className="text-[10px] px-2 py-0.5 rounded bg-amber-500/20 text-amber-400 hover:bg-amber-500/30 font-mono"
                >
                  {modeChanging ? '…' : 'Revert to Shadow'}
                </button>
              )}
            </div>
          }
        />
        {graduation && (
          <>
            <ConfigRow
              label="Readiness"
              value={
                <span
                  className={cn(
                    'font-mono text-[10px]',
                    graduation.ready ? 'text-[var(--to-long)]' : 'text-amber-400'
                  )}
                >
                  {graduation.ready ? 'READY' : 'NOT READY'}
                </span>
              }
            />
            <ConfigRow label="Sample Size" value={`${graduation.metrics.sample_size} / ${graduation.thresholds.min_sample_size}`} />
            <ConfigRow label="Win-Rate Edge" value={`${graduation.metrics.edge_pct.toFixed(1)}% / ${graduation.thresholds.min_edge_pct}%`} />
            <ConfigRow label="AI Blocked (executed)" value={graduation.metrics.sample_size_ai_blocked} />
            <ConfigRow label="AI Allowed" value={graduation.metrics.sample_size_ai_allowed} />
            {!graduation.ready && graduation.reason && (
              <div className="py-2">
                <span className="text-[10px] text-amber-400 font-mono">{graduation.reason}</span>
              </div>
            )}
            <div className="pt-2 border-t border-[#2a2e39]">
              <button
                onClick={() => {
                  setShowToggles(!showToggles);
                  if (!showToggles && toggles.length === 0) loadToggles();
                }}
                className="flex items-center gap-1.5 text-[10px] text-[var(--to-text-dim)] hover:text-[var(--to-text-secondary)] font-mono"
              >
                <History className="w-3 h-3" />
                Toggle History ({toggles.length})
              </button>
              {showToggles && toggles.length > 0 && (
                <div className="mt-2 space-y-1 max-h-32 overflow-y-auto">
                  {toggles.map((t, i) => (
                    <div key={i} className="text-[10px] font-mono text-[var(--to-text-dim)]">
                      {t.from_mode} → {t.to_mode}
                      {t.reason && ` (${t.reason})`}{' '}
                      <span className="text-[var(--to-text-dim)]">{new Date(t.created_at).toLocaleString()}</span>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </>
        )}
      </SectionCard>

      {/* Execution */}
      <SectionCard title="Execution" icon={<Target className="w-4 h-4" />}>
        <ConfigRow
          label="Kill Switch"
          value={
            <StatusBadge
              enabled={execution.trading_kill_switch}
              label={execution.trading_kill_switch ? 'ACTIVE' : 'OFF'}
            />
          }
        />
        <div className="flex items-center justify-between py-2">
          <span className="text-[11px] text-[var(--to-text-dim)] uppercase tracking-wider font-mono">
            Kill Switch History
          </span>
          <button
            type="button"
            onClick={() => {
              const next = !showKillEvents;
              setShowKillEvents(next);
              if (next && killEvents.length === 0) {
                loadKillLog();
              }
            }}
            className="flex items-center gap-1.5 text-[10px] text-[var(--to-text-dim)] hover:text-[var(--to-text-secondary)] font-mono"
          >
            <History className="w-3 h-3" />
            {showKillEvents ? 'Hide' : 'Show'} ({killEvents.length})
          </button>
        </div>
        {showKillEvents && killEvents.length > 0 && (
          <div className="mb-2 max-h-32 space-y-1 overflow-y-auto px-1">
            {killEvents.map((ev) => (
              <div key={ev.id} className="text-[10px] font-mono text-[var(--to-text-dim)]">
                <span className="text-[var(--to-text-dim)]">
                  {new Date(ev.created_at).toLocaleString()}
                </span>
                {' · '}
                <span
                  className={cn(
                    'font-semibold',
                    ev.action === 'engage' ? 'text-[var(--to-short)]' : 'text-[var(--to-long)]',
                  )}
                >
                  {ev.action === 'engage' ? 'HALT' : 'RESET'}
                </span>
                {' by '}
                <span className="text-[var(--to-text-secondary)]">
                  {ev.toggled_by || 'unknown'}
                </span>
                {ev.reason && (
                  <>
                    {' — '}
                    <span className="text-[var(--to-text-dim)]">{ev.reason}</span>
                  </>
                )}
              </div>
            ))}
          </div>
        )}
        <ConfigRow label="Run Mode" value={execution.run_mode} valueClass={
          execution.run_mode === 'LIVE' ? 'text-[var(--to-long)]' :
          execution.run_mode === 'PAPER' ? 'text-amber-400' : 'text-[var(--to-text-dim)]'
        } />
        <ConfigRow label="Execution Mode" value={execution.execution_mode} />
        <ConfigRow label="Live Trading" value={<StatusBadge enabled={execution.live_trading_enabled} />} />
        <ConfigRow label="Shadow Mode" value={<StatusBadge enabled={execution.live_shadow} />} />
        <ConfigRow
          label="MetaAPI"
          value={execution.meta_api_configured ? `Connected (${execution.meta_api_region})` : 'Not configured'}
          valueClass={execution.meta_api_configured ? 'text-[var(--to-long)]' : 'text-[var(--to-text-dim)]'}
        />
      </SectionCard>

      {aiOperatingLayerConfig && (
        <SectionCard
          title="AI Operating Layer"
          icon={<Brain className="w-4 h-4" />}
        >
          <div className="py-3 space-y-3">
            <div className="flex items-center justify-between gap-3">
              <div>
                <div className="text-[11px] text-[var(--to-text-dim)] uppercase tracking-wider font-mono">
                  Panic Mode
                </div>
                <p className="mt-1 text-[11px] text-[var(--to-text-dim)] leading-relaxed">
                  Instantly disable the non-core AI Operating Layer and fall back
                  to the older trusted flow.
                </p>
              </div>
              <button
                type="button"
                onClick={() =>
                  setAiOperatingLayerConfig((current) =>
                    current
                      ? { ...current, panic_mode: !current.panic_mode }
                      : current
                  )
                }
                disabled={aiOperatingLayerSaving}
                className={cn(
                  'rounded px-3 py-1.5 text-[10px] font-mono font-semibold uppercase tracking-wider transition-colors',
                  aiOperatingLayerConfig.panic_mode
                    ? 'bg-rose-600 text-white hover:bg-rose-500'
                    : 'bg-emerald-600 text-white hover:bg-emerald-500'
                )}
              >
                {aiOperatingLayerConfig.panic_mode ? 'ACTIVE' : 'OFF'}
              </button>
            </div>
          </div>

          <div className="py-3 space-y-3">
            <div className="text-[11px] text-[var(--to-text-dim)] uppercase tracking-wider font-mono">
              Global Module States
            </div>
            <div className="space-y-2">
              {moduleEntries.map(([moduleName, moduleState]) => (
                <div
                  key={moduleName}
                  className="flex items-center justify-between gap-3"
                >
                  <span className="font-mono text-xs text-[var(--to-text-secondary)]">
                    {moduleName}
                  </span>
                  <select
                    value={moduleState}
                    onChange={(e) =>
                      setDraftAiOperatingLayerModules((current) => ({
                        ...current,
                        [moduleName]: e.target.value as
                          | 'inherit'
                          | 'enabled'
                          | 'disabled',
                      }))
                    }
                    disabled={aiOperatingLayerSaving}
                    className="rounded border border-[#2a2e39] bg-[#1e222d] px-2 py-1 text-[11px] font-mono text-[var(--to-text-primary)]"
                  >
                    <option value="inherit">inherit</option>
                    <option value="enabled">enabled</option>
                    <option value="disabled">disabled</option>
                  </select>
                </div>
              ))}
            </div>
          </div>

          {draftAiOperatingLayerProvider && (
            <div className="py-3 space-y-3">
              <div className="text-[11px] text-[var(--to-text-dim)] uppercase tracking-wider font-mono">
                Provider Settings
              </div>

              <div className="flex items-center justify-between gap-3">
                <span className="font-mono text-xs text-[var(--to-text-secondary)]">
                  Provider Enabled
                </span>
                <button
                  type="button"
                  onClick={() =>
                    setDraftAiOperatingLayerProvider((current) =>
                      current
                        ? { ...current, enabled: !current.enabled }
                        : current
                    )
                  }
                  disabled={aiOperatingLayerSaving}
                  className={cn(
                    'rounded px-3 py-1.5 text-[10px] font-mono font-semibold uppercase tracking-wider transition-colors',
                    draftAiOperatingLayerProvider.enabled
                      ? 'bg-emerald-600 text-white hover:bg-emerald-500'
                      : 'bg-[var(--to-surface-raised)] text-[var(--to-text-secondary)] hover:bg-[var(--to-surface-raised)]/80'
                  )}
                >
                  {draftAiOperatingLayerProvider.enabled ? 'ON' : 'OFF'}
                </button>
              </div>

              <div className="space-y-2">
                <label className="text-[11px] text-[var(--to-text-dim)] uppercase tracking-wider font-mono">
                  Provider Endpoint
                </label>
                <input
                  data-testid="ai-operating-layer-provider-endpoint"
                  value={draftAiOperatingLayerProvider.base_url}
                  onChange={(e) =>
                    setDraftAiOperatingLayerProvider((current) =>
                      current
                        ? { ...current, base_url: e.target.value }
                        : current
                    )
                  }
                  disabled={aiOperatingLayerSaving}
                  className="w-full rounded border border-[#2a2e39] bg-[#1e222d] px-2 py-1 text-[11px] font-mono text-[var(--to-text-primary)]"
                />
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div className="space-y-2">
                  <label className="text-[11px] text-[var(--to-text-dim)] uppercase tracking-wider font-mono">
                    Timeout Seconds
                  </label>
                  <input
                    type="number"
                    step="0.1"
                    value={draftAiOperatingLayerProvider.timeout_seconds}
                    onChange={(e) =>
                      setDraftAiOperatingLayerProvider((current) =>
                        current
                          ? {
                              ...current,
                              timeout_seconds: Number(e.target.value || 0),
                            }
                          : current
                      )
                    }
                    disabled={aiOperatingLayerSaving}
                    className="w-full rounded border border-[#2a2e39] bg-[#1e222d] px-2 py-1 text-[11px] font-mono text-[var(--to-text-primary)]"
                  />
                </div>
                <div className="space-y-2">
                  <label className="text-[11px] text-[var(--to-text-dim)] uppercase tracking-wider font-mono">
                    Retry Count
                  </label>
                  <input
                    type="number"
                    value={draftAiOperatingLayerProvider.retry_count}
                    onChange={(e) =>
                      setDraftAiOperatingLayerProvider((current) =>
                        current
                          ? {
                              ...current,
                              retry_count: Number(e.target.value || 0),
                            }
                          : current
                      )
                    }
                    disabled={aiOperatingLayerSaving}
                    className="w-full rounded border border-[#2a2e39] bg-[#1e222d] px-2 py-1 text-[11px] font-mono text-[var(--to-text-primary)]"
                  />
                </div>
              </div>
            </div>
          )}

          <div className="py-3 flex items-center justify-between gap-3">
            <p className="text-[11px] text-[var(--to-text-dim)] leading-relaxed">
              These controls are live dashboard config backed by `system_config`,
              not Railway environment variables.
            </p>
            <button
              type="button"
              onClick={handleSaveAiOperatingLayer}
              disabled={aiOperatingLayerSaving}
              className="inline-flex items-center gap-1.5 rounded bg-[var(--to-long)]/20 px-3 py-1.5 text-[10px] font-mono font-semibold text-[var(--to-long)] hover:bg-emerald-500/30"
            >
              <Save className="w-3 h-3" />
              {aiOperatingLayerSaving ? 'Saving…' : 'Save'}
            </button>
          </div>
        </SectionCard>
      )}

      {/* Trinity Risk Engine */}
      <SectionCard title="Trinity Risk Engine" icon={<Shield className="w-4 h-4" />}>
        <ConfigRow label="Status" value={<StatusBadge enabled={risk.trinity_enabled} />} />
        <ConfigRow label="Max Daily Loss" value={`${risk.trinity_max_daily_loss_pct}%`} />
        <ConfigRow label="Max Drawdown" value={`${risk.trinity_max_drawdown_pct}%`} />
        <ConfigRow label="Risk Per Trade" value={`${risk.trinity_max_risk_per_trade_pct}%`} />
        <ConfigRow label="Max Positions" value={risk.trinity_max_positions} />
        <ConfigRow label="Risk %" value={`${risk.risk_percent}%`} />
      </SectionCard>

      {/* Hint */}
      <div className="px-4 py-3 bg-surface border border-panel-border-subtle rounded-lg">
        <p className="text-[11px] text-text-muted leading-relaxed">
          These settings are read from your Railway environment variables.
          To change them, update the environment variables in your Railway project dashboard and redeploy. The AI Operating Layer section above is the exception: those controls are live global config.
        </p>
      </div>
    </div>
  );
}
