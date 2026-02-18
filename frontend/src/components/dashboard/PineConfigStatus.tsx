'use client';

import { useEffect, useRef, useState } from 'react';
import { supabase, isSupabaseAvailable } from '@/lib/supabase';
import { API_BASE_URL } from '@/lib/api';
import { Settings } from 'lucide-react';

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
    // Fallback: fetch backend config (ACCOUNT_BALANCE env) so 50k shows even before next signal
    const fetchBackendConfig = async () => {
      try {
        const res = await fetch(`${API_BASE_URL}/config/ai`);
        if (res.ok) {
          const json: BackendConfig = await res.json();
          const balance = json?.risk?.account_balance;
          if (typeof balance === 'number' && balance > 0) {
            backendBalanceRef.current = balance;
            setConfig((prev) => {
              if (prev?.source === 'tradingview') return prev;
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

    if (!isSupabaseAvailable() || !supabase) {
      return;
    }

    const client = supabase;

    const fetchConfig = async () => {
      const { data } = await client
        .from('trading_signals')
        .select('account_balance, created_at')
        .order('created_at', { ascending: false })
        .limit(1)
        .maybeSingle<SignalData>();

      if (data?.account_balance != null && data.account_balance > 0) {
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
      }
    };

    fetchConfig();

    const channel = client
      .channel('pine-config-updates')
      .on(
        'postgres_changes',
        {
          event: 'INSERT',
          schema: 'public',
          table: 'trading_signals',
        },
        (payload: any) => {
          if (payload.new?.account_balance != null && payload.new.account_balance > 0) {
            setConfig({
              account_balance: payload.new.account_balance,
              updated_at: payload.new.created_at,
              source: 'tradingview',
            });
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
    <div className="tv-card">
      <div className="px-4 py-2.5 flex items-center gap-3">
        <Settings className="w-3.5 h-3.5 text-zinc-500" />
        <span className="font-mono text-[10px] text-zinc-500 uppercase tracking-wider">
          Pine Account Size
        </span>
        <span className="ml-auto font-mono text-sm font-semibold text-[#26a69a] tabular-nums">
          ${config.account_balance.toLocaleString('en-US', { minimumFractionDigits: 2 })}
        </span>
        <span className="font-mono text-[10px] text-zinc-600">
          {config.source === 'tradingview' ? '(from TradingView)' : '(from backend config)'}
        </span>
      </div>
    </div>
  );
}
