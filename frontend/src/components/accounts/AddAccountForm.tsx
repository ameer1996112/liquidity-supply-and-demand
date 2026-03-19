'use client';

import { useState } from 'react';
import { useCreateAccountStrategy } from '@/hooks/useAccountsSupabase';
import { useUpdateChallengeSettings } from '@/hooks/useChallenge';
import { useToast } from '@/components/ui/toast';
import { Button } from '@/components/ui/button';
import { Plus, Loader2, X, ChevronDown, ChevronUp, Shield } from 'lucide-react';

// Bot kill thresholds per provider (set at 80% of firm limits for safety buffer)
const PROVIDER_DEFAULTS: Record<string, { profitTarget: number; dailyLossPct: number; ddPct: number; minDays: number }> = {
  FTMO:       { profitTarget: 5000, dailyLossPct: 4.0, ddPct: 8.0, minDays: 4 },
  ACG:        { profitTarget: 5000, dailyLossPct: 4.0, ddPct: 8.0, minDays: 5 },
  MyFundedFX: { profitTarget: 8000, dailyLossPct: 4.0, ddPct: 8.0, minDays: 5 },
  TFT:        { profitTarget: 5000, dailyLossPct: 4.0, ddPct: 8.0, minDays: 4 },
  E8:         { profitTarget: 8000, dailyLossPct: 4.0, ddPct: 8.0, minDays: 5 },
  Other:      { profitTarget: 5000, dailyLossPct: 4.0, ddPct: 8.0, minDays: 4 },
};

interface AddAccountFormProps {
  onSuccess?: () => void;
  onCancel?: () => void;
}

export function AddAccountForm({ onSuccess, onCancel }: AddAccountFormProps) {
  const { addToast } = useToast();
  const createAccount = useCreateAccountStrategy();

  // Basic fields
  const [accountName, setAccountName] = useState('');
  const [accountType, setAccountType] = useState('Personal');
  const [provider, setProvider] = useState('Personal');
  const [strategyType, setStrategyType] = useState('BALANCED');
  const [riskPercent, setRiskPercent] = useState(0.5);
  const [maxPositions, setMaxPositions] = useState(3);
  const [allocatedCapital, setAllocatedCapital] = useState(50000);

  // MetaAPI connection
  const [metaApiAccountId, setMetaApiAccountId] = useState('');
  const [metaApiTokenKey, setMetaApiTokenKey] = useState('META_API_TOKEN');

  // Risk settings (shown for Eval/Funded)
  const [profitTarget, setProfitTarget] = useState(5000);
  const [dailyLossPct, setDailyLossPct] = useState(4.0);
  const [ddPct, setDdPct] = useState(8.0);
  const [minDays, setMinDays] = useState(4);

  // Advanced toggle
  const [showAdvanced, setShowAdvanced] = useState(false);

  const isEvalOrFunded = accountType === 'Eval' || accountType === 'Funded';

  // When provider changes, pre-fill challenge limits with that firm's defaults
  const handleProviderChange = (p: string) => {
    setProvider(p);
    const defaults = PROVIDER_DEFAULTS[p];
    if (defaults && isEvalOrFunded) {
      setProfitTarget(defaults.profitTarget);
      setDailyLossPct(defaults.dailyLossPct);
      setDdPct(defaults.ddPct);
      setMinDays(defaults.minDays);
    }
  };

  // When account type changes, reset provider and pre-fill defaults
  const handleTypeChange = (t: string) => {
    setAccountType(t);
    if (t === 'Personal') {
      setProvider('Personal');
    } else {
      if (provider === 'Personal') setProvider('FTMO');
      const p = provider === 'Personal' ? 'FTMO' : provider;
      const defaults = PROVIDER_DEFAULTS[p];
      if (defaults) {
        setProfitTarget(defaults.profitTarget);
        setDailyLossPct(defaults.dailyLossPct);
        setDdPct(defaults.ddPct);
        setMinDays(defaults.minDays);
      }
    }
  };

  // Hook to save challenge settings after account creation
  const [createdAccountName, setCreatedAccountName] = useState('');
  const updateChallenge = useUpdateChallengeSettings(createdAccountName);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    const name = accountName.trim();
    if (!name) {
      addToast({ title: 'Validation', message: 'Account name is required', severity: 'warning', duration: 3000 });
      return;
    }
    try {
      await createAccount.mutateAsync({
        account_name: name,
        account_type: accountType,
        provider: provider,
        strategy_type: strategyType,
        risk_percent: riskPercent,
        max_positions: maxPositions,
        allocated_capital_usd: allocatedCapital,
        meta_api_account_id: metaApiAccountId.trim() || undefined,
        meta_api_token_env_key: metaApiTokenKey.trim() || undefined,
      });

      // Save challenge settings for Eval/Funded accounts
      if (isEvalOrFunded) {
        setCreatedAccountName(name);
        // Small delay to let the account be created and broker_profile linked
        await new Promise(r => setTimeout(r, 500));
        try {
          await updateChallenge.mutateAsync({
            evaluation_mode: true,
            evaluation_phase: 'phase1',
            starting_balance: allocatedCapital,
            profit_target: profitTarget,
            max_daily_loss_pct: dailyLossPct,
            max_drawdown_pct: ddPct,
            min_trading_days: minDays,
            consistency_limit_pct: 40,
          });
        } catch {
          // Non-fatal: challenge settings can be edited later in the Challenge tab
        }
      }

      addToast({
        title: 'Account added',
        message: `${name} created${isEvalOrFunded ? ` — ${provider} configuration applied` : ''}`,
        severity: 'success',
        duration: 4000,
      });

      // Reset form
      setAccountName('');
      setAccountType('Personal');
      setProvider('Personal');
      setStrategyType('BALANCED');
      setRiskPercent(0.5);
      setMaxPositions(3);
      setAllocatedCapital(50000);
      setMetaApiAccountId('');
      setMetaApiTokenKey('META_API_TOKEN');
      setProfitTarget(5000);
      setDailyLossPct(4.0);
      setDdPct(8.0);
      setMinDays(4);
      setShowAdvanced(false);
      onSuccess?.();
    } catch (err) {
      const msg = err instanceof Error ? err.message : String(err);
      addToast({ title: 'Failed to add account', message: msg || 'Unknown error. Check backend logs.', severity: 'critical', duration: 6000 });
    }
  };

  return (
    <form
      onSubmit={handleSubmit}
      className='rounded-lg border border-[#2a2e39] bg-[#1e222d]/80 p-4 space-y-4'
    >
      <div className='flex items-center justify-between'>
        <h3 className='text-sm font-semibold text-[var(--to-text-primary)]'>Add account</h3>
        {onCancel && (
          <button
            type='button'
            onClick={onCancel}
            className='text-[var(--to-text-dim)] hover:text-[var(--to-text-secondary)]'
          >
            <X className='h-4 w-4' />
          </button>
        )}
      </div>

      {/* Account name */}
      <div>
        <label className='text-[10px] text-[var(--to-text-dim)] font-mono block mb-1'>
          Account name *
        </label>
        <input
          id='account-name'
          type='text'
          value={accountName}
          onChange={(e) => setAccountName(e.target.value)}
          placeholder='e.g. ACG Stage 1, FTMO Challenge'
          className='w-full px-3 py-2 bg-[#1e222d] border border-[#2a2e39] rounded text-sm text-[var(--to-text-primary)] font-mono placeholder:text-[var(--to-text-dim)] focus:outline-none focus:border-zinc-500'
          required
        />
      </div>

      {/* Account Type + Provider */}
      <div className='grid grid-cols-2 gap-3'>
        <div>
          <label className='text-[10px] text-[var(--to-text-dim)] font-mono block mb-1'>
            Account type
          </label>
          <select
            id='account-type'
            value={accountType}
            onChange={(e) => handleTypeChange(e.target.value)}
            className='w-full px-3 py-2 bg-[#1e222d] border border-[#2a2e39] rounded text-sm text-[var(--to-text-primary)] font-mono'
          >
            <option value='Personal'>Personal</option>
            <option value='Eval'>Evaluation</option>
            <option value='Funded'>Funded</option>
          </select>
        </div>
        <div>
          <label className='text-[10px] text-[var(--to-text-dim)] font-mono block mb-1'>
            Provider
          </label>
          <select
            id='account-provider'
            value={provider}
            onChange={(e) => handleProviderChange(e.target.value)}
            className='w-full px-3 py-2 bg-[#1e222d] border border-[#2a2e39] rounded text-sm text-[var(--to-text-primary)] font-mono'
          >
            <option value='Personal'>Personal</option>
            <option value='FTMO'>FTMO</option>
            <option value='ACG'>Alpha Capital Group</option>
            <option value='MyFundedFX'>MyFundedFX</option>
            <option value='TFT'>The Funded Trader</option>
            <option value='E8'>E8 Funding</option>
            <option value='Other'>Other</option>
          </select>
        </div>
      </div>

      {/* Strategy + Risk */}
      <div className='grid grid-cols-2 gap-3'>
        <div>
          <label className='text-[10px] text-[var(--to-text-dim)] font-mono block mb-1'>
            Strategy type
          </label>
          <select
            id='account-strategy-type'
            value={strategyType}
            onChange={(e) => setStrategyType(e.target.value)}
            className='w-full px-3 py-2 bg-[#1e222d] border border-[#2a2e39] rounded text-sm text-[var(--to-text-primary)] font-mono'
          >
            <option value='CONSERVATIVE'>Conservative</option>
            <option value='BALANCED'>Balanced</option>
            <option value='AGGRESSIVE'>Aggressive</option>
            <option value='CUSTOM'>Custom</option>
          </select>
        </div>
        <div>
          <label className='text-[10px] text-[var(--to-text-dim)] font-mono block mb-1'>
            Risk %
          </label>
          <input
            id='account-risk-percent'
            type='number'
            min={0.1}
            max={5}
            step={0.1}
            value={riskPercent}
            onChange={(e) => setRiskPercent(parseFloat(e.target.value) || 0)}
            className='w-full px-3 py-2 bg-[#1e222d] border border-[#2a2e39] rounded text-sm font-mono text-[var(--to-text-primary)]'
          />
        </div>
      </div>

      {/* Max Positions + Capital */}
      <div className='grid grid-cols-2 gap-3'>
        <div>
          <label className='text-[10px] text-[var(--to-text-dim)] font-mono block mb-1'>
            Max positions
          </label>
          <input
            id='account-max-positions'
            type='number'
            min={1}
            max={10}
            value={maxPositions}
            onChange={(e) => setMaxPositions(parseInt(e.target.value, 10) || 0)}
            className='w-full px-3 py-2 bg-[#1e222d] border border-[#2a2e39] rounded text-sm font-mono text-[var(--to-text-primary)]'
          />
        </div>
        <div>
          <label className='text-[10px] text-[var(--to-text-dim)] font-mono block mb-1'>
            Starting capital ($)
          </label>
          <input
            id='account-allocated-capital'
            type='number'
            min={0}
            step={100}
            value={allocatedCapital}
            onChange={(e) =>
              setAllocatedCapital(parseFloat(e.target.value) || 0)
            }
            className='w-full px-3 py-2 bg-[#1e222d] border border-[#2a2e39] rounded text-sm font-mono text-[var(--to-text-primary)]'
          />
        </div>
      </div>

      {/* MetaAPI Connection */}
      <div>
        <label className='text-[10px] text-[var(--to-text-dim)] font-mono block mb-1'>
          MetaAPI Account ID
        </label>
        <input
          id='account-metaapi-id'
          type='text'
          value={metaApiAccountId}
          onChange={(e) => setMetaApiAccountId(e.target.value)}
          placeholder='Paste your MetaAPI account ID (optional)'
          className='w-full px-3 py-2 bg-[#1e222d] border border-[#2a2e39] rounded text-sm text-[var(--to-text-primary)] font-mono placeholder:text-[var(--to-text-dim)] focus:outline-none focus:border-zinc-500'
        />
        <p className='text-[9px] text-[var(--to-text-dim)] mt-1'>
          Connect to your broker via MetaAPI. Leave empty to configure later.
        </p>
      </div>

      {/* Advanced Settings Toggle */}
      <button
        type='button'
        onClick={() => setShowAdvanced(!showAdvanced)}
        className='flex items-center gap-1 text-[10px] text-[var(--to-text-dim)] hover:text-[var(--to-text-dim)] font-mono transition-colors'
      >
        {showAdvanced ? (
          <ChevronUp className='h-3 w-3' />
        ) : (
          <ChevronDown className='h-3 w-3' />
        )}
        Advanced settings
      </button>

      {showAdvanced && (
        <div className='space-y-3 pl-2 border-l border-[#2a2e39]'>
          <div>
            <label className='text-[10px] text-[var(--to-text-dim)] font-mono block mb-1'>
              Token env key
            </label>
            <input
              id='account-metaapi-token-key'
              type='text'
              value={metaApiTokenKey}
              onChange={(e) => setMetaApiTokenKey(e.target.value)}
              placeholder='META_API_TOKEN'
              className='w-full px-3 py-2 bg-[#1e222d] border border-[#2a2e39] rounded text-sm text-[var(--to-text-primary)] font-mono placeholder:text-[var(--to-text-dim)] focus:outline-none focus:border-zinc-500'
            />
            <p className='text-[9px] text-[var(--to-text-dim)] mt-1'>
              Environment variable name holding the MetaAPI JWT. Default:
              META_API_TOKEN
            </p>
          </div>
        </div>
      )}

      {/* Risk Guardrails (Eval / Funded only) */}
      {isEvalOrFunded && (
        <div className='rounded-lg border border-[#2a2e39] bg-[#1a1d24] p-3 space-y-3 mt-4'>
          <div className='flex items-center gap-2'>
            <Shield className='h-3.5 w-3.5 text-yellow-500/80' />
            <span className='text-xs font-semibold text-[var(--to-text-secondary)]'>Risk Guardrails</span>
            <span className='text-[9px] text-[var(--to-text-dim)] font-mono ml-1'>
              (pre-filled for {provider === 'Personal' ? 'FTMO' : provider} — edit below or adjust later)
            </span>
          </div>

          <div className='grid grid-cols-2 gap-2'>
            <div>
              <label className='text-[10px] text-[var(--to-text-dim)] font-mono block mb-1'>Profit Target ($)</label>
              <input type='number' min={0} step={500} value={profitTarget}
                onChange={e => setProfitTarget(parseFloat(e.target.value) || 0)}
                className='w-full px-2 py-1.5 bg-[#1e222d] border border-[#2a2e39] rounded text-sm font-mono text-[var(--to-text-primary)] focus:outline-none focus:border-zinc-500' />
            </div>
            <div>
              <label className='text-[10px] text-[var(--to-text-dim)] font-mono block mb-1'>
                Daily Kill % <span className='text-[var(--to-text-dim)]'>(bot stop)</span>
              </label>
              <input type='number' min={0.5} max={10} step={0.5} value={dailyLossPct}
                onChange={e => setDailyLossPct(parseFloat(e.target.value) || 0)}
                className='w-full px-2 py-1.5 bg-[#1e222d] border border-[#2a2e39] rounded text-sm font-mono text-[var(--to-text-primary)] focus:outline-none focus:border-zinc-500' />
              <p className='text-[9px] text-[var(--to-text-dim)] mt-0.5 font-mono'>
                = ${((allocatedCapital * dailyLossPct) / 100).toLocaleString(undefined, { maximumFractionDigits: 0 })}
              </p>
            </div>
            <div>
              <label className='text-[10px] text-[var(--to-text-dim)] font-mono block mb-1'>
                Drawdown Kill % <span className='text-[var(--to-text-dim)]'>(bot stop)</span>
              </label>
              <input type='number' min={1} max={20} step={0.5} value={ddPct}
                onChange={e => setDdPct(parseFloat(e.target.value) || 0)}
                className='w-full px-2 py-1.5 bg-[#1e222d] border border-[#2a2e39] rounded text-sm font-mono text-[var(--to-text-primary)] focus:outline-none focus:border-zinc-500' />
              <p className='text-[9px] text-[var(--to-text-dim)] mt-0.5 font-mono'>
                = ${((allocatedCapital * ddPct) / 100).toLocaleString(undefined, { maximumFractionDigits: 0 })}
              </p>
            </div>
            <div>
              <label className='text-[10px] text-[var(--to-text-dim)] font-mono block mb-1'>Min Trading Days</label>
              <input type='number' min={0} max={60} step={1} value={minDays}
                onChange={e => setMinDays(parseInt(e.target.value, 10) || 0)}
                className='w-full px-2 py-1.5 bg-[#1e222d] border border-[#2a2e39] rounded text-sm font-mono text-[var(--to-text-primary)] focus:outline-none focus:border-zinc-500' />
            </div>
          </div>
        </div>
      )}

      {/* Submit */}
      <div className='flex gap-2 pt-2'>
        <Button type='submit' size='sm' disabled={createAccount.isPending}>
          {createAccount.isPending ? (
            <Loader2 className='h-3.5 w-3.5 animate-spin mr-2' />
          ) : (
            <Plus className='h-3.5 w-3.5 mr-2' />
          )}
          Add account
        </Button>
        {onCancel && (
          <Button type='button' variant='ghost' size='sm' onClick={onCancel}>
            Cancel
          </Button>
        )}
      </div>
    </form>
  );
}
