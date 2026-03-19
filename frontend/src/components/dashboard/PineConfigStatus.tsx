'use client';

import { useEffect, useRef, useState } from 'react';
import { supabase, isSupabaseAvailable } from '@/lib/supabase';
import { API_BASE_URL } from '@/lib/api';
import { Cpu } from 'lucide-react';

/** Below this (USD), TradingView value is treated as implausible and backend config is shown instead. */
const MIN_PLAUSIBLE_ACCOUNT_USD = 100;

interface PineConfig {
  account_balance: number;
  updated_at: string;
  source: 'tradingview' | 'backend';
}

interface SignalData {
  account_balance: number;
  created_at: string;
}

interface BackendConfig {
  risk?: { account_balance?: number };
}

export function PineConfigStatus() {
  const [config, setConfig] = useState<PineConfig | null>(null);
  const backendBalanceRef = useRef<number | null>(null);

  useEffect(() => {
    const fetchBackendConfig = async () => {
      try {
        const res = await fetch(`${API_BASE_URL}/config/ai`);
        if (res.ok) {
          const json: BackendConfig = await res.json();
          const balance = json?.risk?.account_balance;
          if (typeof balance === 'number' && balance > 0) {
            backendBalanceRef.current = balance;
            setConfig((prev) => {
              const keepTv =
                prev?.source === 'tradingview' &&
                (prev?.account_balance ?? 0) >= MIN_PLAUSIBLE_ACCOUNT_USD;
              if (keepTv) return prev;
              return {
                account_balance: balance,
                updated_at: '',
                source: 'backend',
              };
            });
          }
        }
      } catch {
        // Backend may be unavailable; ignore
      }
    };
    fetchBackendConfig();

    if (!isSupabaseAvailable() || !supabase) return;

    const client = supabase;

    const fetchConfig = async () => {
      const { data } = await client
        .from('trading_signals')
        .select('account_balance, created_at')
        .order('created_at', { ascending: false })
        .limit(1)
        .maybeSingle<SignalData>();

      if (data?.account_balance != null && data.account_balance > 0) {
        const plausible =
          data.account_balance >= MIN_PLAUSIBLE_ACCOUNT_USD;
        if (plausible) {
          setConfig({
            account_balance: data.account_balance,
            updated_at: data.created_at,
            source: 'tradingview',
          });
        } else if (backendBalanceRef.current != null) {
          setConfig({
            account_balance: backendBalanceRef.current,
            updated_at: '',
            source: 'backend',
          });
        } else {
          setConfig({
            account_balance: data.account_balance,
            updated_at: data.created_at,
            source: 'tradingview',
          });
        }
      } else if (backendBalanceRef.current != null) {
        setConfig({
          account_balance: backendBalanceRef.current,
          updated_at: '',
          source: 'backend',
        });
      }
    };

    fetchConfig();

    const channel = client
      .channel('pine-config-updates')
      .on(
        'postgres_changes',
        { event: 'INSERT', schema: 'public', table: 'trading_signals' },
        (payload: any) => {
          if (
            payload.new?.account_balance != null &&
            payload.new.account_balance > 0
          ) {
            const fromTv = payload.new.account_balance as number;
            const plausible = fromTv >= MIN_PLAUSIBLE_ACCOUNT_USD;
            if (plausible) {
              setConfig({
                account_balance: fromTv,
                updated_at: payload.new.created_at,
                source: 'tradingview',
              });
            } else if (backendBalanceRef.current != null) {
              setConfig({
                account_balance: backendBalanceRef.current,
                updated_at: '',
                source: 'backend',
              });
            } else {
              setConfig({
                account_balance: fromTv,
                updated_at: payload.new.created_at,
                source: 'tradingview',
              });
            }
          }
        }
      )
      .subscribe();

    return () => {
      client.removeChannel(channel);
    };
  }, []);

  if (!config) return null;

  return (
    <div className='flex items-center gap-2.5 rounded-lg border border-slate-700/60 bg-slate-800/50 px-3 py-2'>
      <Cpu className='h-3.5 w-3.5 shrink-0 text-[var(--to-text-dim)]' />
      <span className='status-dot status-dot-active pulse-active shrink-0' />
      <span
        className='text-[10px] uppercase tracking-[0.12em] text-[var(--to-text-dim)]'
        style={{ fontFamily: 'var(--font-sans)' }}
      >
        Account Size
      </span>
      <span
        className='ml-auto text-sm font-semibold tabular-nums text-[var(--to-long)]'
        style={{ fontFamily: 'var(--font-mono)' }}
      >
        $
        {config.account_balance.toLocaleString('en-US', {
          minimumFractionDigits: 2,
        })}
      </span>
      <span
        className='text-[9px] text-[var(--to-text-dim)]'
        style={{ fontFamily: 'var(--font-mono)' }}
      >
        {config.source === 'tradingview' ? 'TV' : 'CFG'}
      </span>
    </div>
  );
}
