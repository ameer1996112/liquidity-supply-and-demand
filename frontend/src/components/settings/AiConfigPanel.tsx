'use client';

import { useEffect, useState } from 'react';
import { AiConfigResponse, fetchAiConfig } from '@/lib/api';
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
  const [state, setState] = useState<LoadState>('loading');
  const [error, setError] = useState('');

  const load = () => {
    setState('loading');
    setError('');
    fetchAiConfig()
      .then((data) => {
        setConfig(data);
        setState('loaded');
      })
      .catch((err) => {
        setError(err instanceof Error ? err.message : 'Failed to load');
        setState('error');
      });
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
        <ConfigRow label="Account Balance" value={`$${risk.account_balance.toLocaleString()}`} />
        <ConfigRow label="Risk %" value={`${risk.risk_percent}%`} />
        <ConfigRow label="Risk Scaling" value={<StatusBadge enabled={risk.enable_risk_scaling} />} />
        <ConfigRow label="Risk Mode" value={risk.risk_mode.toUpperCase()} />
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
