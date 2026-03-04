'use client';

import { useEffect, useState } from 'react';
import {
  AiConfigResponse,
  fetchAiConfig,
  fetchGraduationStatus,
  fetchAiModeToggles,
  setAiMode,
  GraduationReadiness,
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
} from 'lucide-react';

type LoadState = 'loading' | 'loaded' | 'error';

function StatusBadge({ enabled, label }: { enabled: boolean; label?: string }) {
  return (
    <span
      className={cn(
        'inline-flex items-center gap-1 font-mono text-[10px] px-1.5 py-0.5 rounded',
        enabled ? 'text-emerald-400 bg-emerald-500/10' : 'text-zinc-500 bg-zinc-700/30'
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
      <span className="text-[11px] text-zinc-500 uppercase tracking-wider font-mono">{label}</span>
      <span className={cn('font-mono text-xs text-zinc-300', valueClass)}>{value}</span>
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
    <div className="tv-card">
      <div className="px-4 py-3 border-b border-[#2a2e39]">
        <div className="flex items-center gap-2">
          <div className="text-zinc-500">{icon}</div>
          <span className="font-mono text-xs text-zinc-400 uppercase tracking-wider">{title}</span>
        </div>
      </div>
      <div className="px-4 py-2 divide-y divide-[#2a2e39]">{children}</div>
    </div>
  );
}

export function AiConfigPanel() {
  const [config, setConfig] = useState<AiConfigResponse | null>(null);
  const [graduation, setGraduation] = useState<GraduationReadiness | null>(null);
  const [state, setState] = useState<LoadState>('loading');
  const [error, setError] = useState('');
  const [modeChanging, setModeChanging] = useState(false);
  const [showEnforceConfirm, setShowEnforceConfirm] = useState(false);
  const [toggles, setToggles] = useState<Array<{ from_mode: string; to_mode: string; reason: string | null; created_at: string }>>([]);
  const [showToggles, setShowToggles] = useState(false);

  const load = () => {
    setState('loading');
    setError('');
    Promise.all([fetchAiConfig(), fetchGraduationStatus()])
      .then(([data, grad]) => {
        setConfig(data);
        setGraduation(grad);
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

  useEffect(() => {
    load();
  }, []);

  if (state === 'loading') {
    return (
      <div className="tv-card p-8 flex items-center justify-center">
        <Loader2 className="w-5 h-5 text-zinc-500 animate-spin" />
        <span className="ml-2 text-sm text-zinc-500 font-mono">Loading AI configuration...</span>
      </div>
    );
  }

  if (state === 'error') {
    return (
      <div className="tv-card p-6 flex flex-col items-center justify-center gap-3">
        <AlertTriangle className="w-8 h-8 text-amber-500" />
        <span className="text-sm text-zinc-400 font-mono">{error}</span>
        <p className="text-[11px] text-zinc-600 text-center max-w-md">
          Cannot reach backend API. Make sure NEXT_PUBLIC_API_URL is set and the Railway backend is running.
          AI/ML settings are configured via Railway environment variables.
        </p>
        <button
          onClick={load}
          className="flex items-center gap-1.5 px-3 py-1.5 bg-[#2a2e39] rounded text-xs text-zinc-300 hover:bg-[#363a45] transition-colors font-mono"
        >
          <RefreshCw className="w-3 h-3" />
          Retry
        </button>
      </div>
    );
  }

  if (!config) return null;

  const { ai, ml, ensemble, execution, risk } = config;

  return (
    <div className="space-y-4">
      {/* Header with refresh */}
      <div className="flex items-center justify-between">
        <span className="font-mono text-xs text-zinc-400 uppercase tracking-wider">
          Live Configuration from Railway
        </span>
        <button
          onClick={load}
          className="flex items-center gap-1.5 text-[10px] text-zinc-500 hover:text-zinc-300 transition-colors font-mono"
        >
          <RefreshCw className="w-3 h-3" />
          Refresh
        </button>
      </div>

      {/* AI Guardian */}
      <SectionCard title="AI Guardian (LLM)" icon={<Brain className="w-4 h-4" />}>
        <ConfigRow label="Status" value={<StatusBadge enabled={ai.ai_filter_enabled} />} />
        <ConfigRow label="Provider" value={ai.ai_provider.toUpperCase()} />
        <ConfigRow label="Model" value={ai.ai_model} />
        <ConfigRow label="Base URL" value={ai.ai_base_url} />
        <ConfigRow label="Min Confidence" value={`${ai.ai_min_confidence}%`} />
        <ConfigRow label="Timeout" value={`${ai.ai_timeout_seconds}s`} />
        <ConfigRow
          label="API Key"
          value={ai.ai_api_key_set ? 'Configured' : 'Not set'}
          valueClass={ai.ai_api_key_set ? 'text-emerald-400' : 'text-rose-400'}
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
                      className="text-[10px] px-2 py-0.5 rounded bg-emerald-500/20 text-emerald-400 hover:bg-emerald-500/30 font-mono"
                    >
                      Enable Enforce
                    </button>
                  ) : (
                    <div className="flex items-center gap-1">
                      <button
                        onClick={handleSetEnforce}
                        disabled={modeChanging}
                        className="text-[10px] px-2 py-0.5 rounded bg-emerald-500/30 text-emerald-400 font-mono"
                      >
                        {modeChanging ? '…' : 'Confirm'}
                      </button>
                      <button
                        onClick={() => setShowEnforceConfirm(false)}
                        disabled={modeChanging}
                        className="text-[10px] px-2 py-0.5 rounded bg-zinc-600 text-zinc-300 font-mono"
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
                    graduation.ready ? 'text-emerald-400' : 'text-amber-400'
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
                className="flex items-center gap-1.5 text-[10px] text-zinc-500 hover:text-zinc-300 font-mono"
              >
                <History className="w-3 h-3" />
                Toggle History ({toggles.length})
              </button>
              {showToggles && toggles.length > 0 && (
                <div className="mt-2 space-y-1 max-h-32 overflow-y-auto">
                  {toggles.map((t, i) => (
                    <div key={i} className="text-[10px] font-mono text-zinc-500">
                      {t.from_mode} → {t.to_mode}
                      {t.reason && ` (${t.reason})`}{' '}
                      <span className="text-zinc-600">{new Date(t.created_at).toLocaleString()}</span>
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
        <ConfigRow label="Run Mode" value={execution.run_mode} valueClass={
          execution.run_mode === 'LIVE' ? 'text-emerald-400' :
          execution.run_mode === 'PAPER' ? 'text-amber-400' : 'text-zinc-500'
        } />
        <ConfigRow label="Execution Mode" value={execution.execution_mode} />
        <ConfigRow label="Live Trading" value={<StatusBadge enabled={execution.live_trading_enabled} />} />
        <ConfigRow label="Shadow Mode" value={<StatusBadge enabled={execution.live_shadow} />} />
        <ConfigRow
          label="MetaAPI"
          value={execution.meta_api_configured ? `Connected (${execution.meta_api_region})` : 'Not configured'}
          valueClass={execution.meta_api_configured ? 'text-emerald-400' : 'text-zinc-500'}
        />
      </SectionCard>

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
      <div className="px-4 py-3 bg-[#1e222d] border border-[#2a2e39] rounded-lg">
        <p className="text-[11px] text-zinc-500 leading-relaxed">
          These settings are read from your Railway environment variables.
          To change them, update the environment variables in your Railway project dashboard and redeploy.
        </p>
      </div>
    </div>
  );
}
