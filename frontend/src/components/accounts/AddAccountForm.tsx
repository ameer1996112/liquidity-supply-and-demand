'use client';

import { useState } from 'react';
import { useCreateAccountStrategy } from '@/hooks/useAccountsSupabase';
import { useToast } from '@/components/ui/toast';
import { Button } from '@/components/ui/button';
import { Plus, Loader2, X, ChevronDown, ChevronUp } from 'lucide-react';

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
  const [riskPercent, setRiskPercent] = useState(1);
  const [maxPositions, setMaxPositions] = useState(3);
  const [allocatedCapital, setAllocatedCapital] = useState(50000);

  // MetaAPI connection
  const [metaApiAccountId, setMetaApiAccountId] = useState('');
  const [metaApiTokenKey, setMetaApiTokenKey] = useState('META_API_TOKEN');

  // Advanced toggle
  const [showAdvanced, setShowAdvanced] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    const name = accountName.trim();
    if (!name) {
      addToast({
        title: 'Validation',
        message: 'Account name is required',
        severity: 'warning',
        duration: 3000,
      });
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
      addToast({
        title: 'Account added',
        message: `${name} created successfully${metaApiAccountId.trim() ? ' with broker profile' : ''}`,
        severity: 'success',
        duration: 3000,
      });
      // Reset
      setAccountName('');
      setAccountType('Personal');
      setProvider('Personal');
      setStrategyType('BALANCED');
      setRiskPercent(1);
      setMaxPositions(3);
      setAllocatedCapital(50000);
      setMetaApiAccountId('');
      setMetaApiTokenKey('META_API_TOKEN');
      setShowAdvanced(false);
      onSuccess?.();
    } catch (err) {
      const msg = err instanceof Error ? err.message : String(err);
      addToast({
        title: 'Failed to add account',
        message: msg || 'Unknown error. Check backend logs.',
        severity: 'critical',
        duration: 6000,
      });
    }
  };

  return (
    <form
      onSubmit={handleSubmit}
      className='rounded-lg border border-[#2a2e39] bg-[#1e222d]/80 p-4 space-y-4'
    >
      <div className='flex items-center justify-between'>
        <h3 className='text-sm font-semibold text-zinc-200'>Add account</h3>
        {onCancel && (
          <button
            type='button'
            onClick={onCancel}
            className='text-zinc-500 hover:text-zinc-300'
          >
            <X className='h-4 w-4' />
          </button>
        )}
      </div>

      {/* Account name */}
      <div>
        <label className='text-[10px] text-zinc-500 font-mono block mb-1'>
          Account name *
        </label>
        <input
          id='account-name'
          type='text'
          value={accountName}
          onChange={(e) => setAccountName(e.target.value)}
          placeholder='e.g. ACG Stage 1, FTMO Challenge'
          className='w-full px-3 py-2 bg-[#1e222d] border border-[#2a2e39] rounded text-sm text-zinc-200 font-mono placeholder:text-zinc-600 focus:outline-none focus:border-zinc-500'
          required
        />
      </div>

      {/* Account Type + Provider */}
      <div className='grid grid-cols-2 gap-3'>
        <div>
          <label className='text-[10px] text-zinc-500 font-mono block mb-1'>
            Account type
          </label>
          <select
            id='account-type'
            value={accountType}
            onChange={(e) => {
              setAccountType(e.target.value);
              if (e.target.value === 'Personal') setProvider('Personal');
            }}
            className='w-full px-3 py-2 bg-[#1e222d] border border-[#2a2e39] rounded text-sm text-zinc-200 font-mono'
          >
            <option value='Personal'>Personal</option>
            <option value='Eval'>Evaluation</option>
            <option value='Funded'>Funded</option>
          </select>
        </div>
        <div>
          <label className='text-[10px] text-zinc-500 font-mono block mb-1'>
            Provider
          </label>
          <select
            id='account-provider'
            value={provider}
            onChange={(e) => setProvider(e.target.value)}
            className='w-full px-3 py-2 bg-[#1e222d] border border-[#2a2e39] rounded text-sm text-zinc-200 font-mono'
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
          <label className='text-[10px] text-zinc-500 font-mono block mb-1'>
            Strategy type
          </label>
          <select
            id='account-strategy-type'
            value={strategyType}
            onChange={(e) => setStrategyType(e.target.value)}
            className='w-full px-3 py-2 bg-[#1e222d] border border-[#2a2e39] rounded text-sm text-zinc-200 font-mono'
          >
            <option value='CONSERVATIVE'>Conservative</option>
            <option value='BALANCED'>Balanced</option>
            <option value='AGGRESSIVE'>Aggressive</option>
            <option value='CUSTOM'>Custom</option>
          </select>
        </div>
        <div>
          <label className='text-[10px] text-zinc-500 font-mono block mb-1'>
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
            className='w-full px-3 py-2 bg-[#1e222d] border border-[#2a2e39] rounded text-sm font-mono text-zinc-200'
          />
        </div>
      </div>

      {/* Max Positions + Capital */}
      <div className='grid grid-cols-2 gap-3'>
        <div>
          <label className='text-[10px] text-zinc-500 font-mono block mb-1'>
            Max positions
          </label>
          <input
            id='account-max-positions'
            type='number'
            min={1}
            max={10}
            value={maxPositions}
            onChange={(e) => setMaxPositions(parseInt(e.target.value, 10) || 0)}
            className='w-full px-3 py-2 bg-[#1e222d] border border-[#2a2e39] rounded text-sm font-mono text-zinc-200'
          />
        </div>
        <div>
          <label className='text-[10px] text-zinc-500 font-mono block mb-1'>
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
            className='w-full px-3 py-2 bg-[#1e222d] border border-[#2a2e39] rounded text-sm font-mono text-zinc-200'
          />
        </div>
      </div>

      {/* MetaAPI Connection */}
      <div>
        <label className='text-[10px] text-zinc-500 font-mono block mb-1'>
          MetaAPI Account ID
        </label>
        <input
          id='account-metaapi-id'
          type='text'
          value={metaApiAccountId}
          onChange={(e) => setMetaApiAccountId(e.target.value)}
          placeholder='Paste your MetaAPI account ID (optional)'
          className='w-full px-3 py-2 bg-[#1e222d] border border-[#2a2e39] rounded text-sm text-zinc-200 font-mono placeholder:text-zinc-600 focus:outline-none focus:border-zinc-500'
        />
        <p className='text-[9px] text-zinc-600 mt-1'>
          Connect to your broker via MetaAPI. Leave empty to configure later.
        </p>
      </div>

      {/* Advanced Settings Toggle */}
      <button
        type='button'
        onClick={() => setShowAdvanced(!showAdvanced)}
        className='flex items-center gap-1 text-[10px] text-zinc-500 hover:text-zinc-400 font-mono transition-colors'
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
            <label className='text-[10px] text-zinc-500 font-mono block mb-1'>
              Token env key
            </label>
            <input
              id='account-metaapi-token-key'
              type='text'
              value={metaApiTokenKey}
              onChange={(e) => setMetaApiTokenKey(e.target.value)}
              placeholder='META_API_TOKEN'
              className='w-full px-3 py-2 bg-[#1e222d] border border-[#2a2e39] rounded text-sm text-zinc-200 font-mono placeholder:text-zinc-600 focus:outline-none focus:border-zinc-500'
            />
            <p className='text-[9px] text-zinc-600 mt-1'>
              Environment variable name holding the MetaAPI JWT. Default:
              META_API_TOKEN
            </p>
          </div>
        </div>
      )}

      {/* Evaluation notice */}
      {accountType === 'Eval' && (
        <div className='rounded border border-blue-500/30 bg-blue-500/5 px-3 py-2'>
          <p className='text-[10px] text-blue-400'>
            Evaluation mode will be enabled. The bot will enforce daily loss
            (5%) and max drawdown (10%) limits per FTMO rules. You can customize
            limits in the account settings after creation.
          </p>
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
