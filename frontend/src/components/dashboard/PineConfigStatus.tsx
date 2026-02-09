'use client';

import { useEffect, useState } from 'react';
import { supabase, isSupabaseAvailable } from '@/lib/supabase';
import { Settings } from 'lucide-react';

interface PineConfig {
  account_balance: number;
  updated_at: string;
}

export function PineConfigStatus() {
  const [config, setConfig] = useState<PineConfig | null>(null);

  useEffect(() => {
    if (!isSupabaseAvailable() || !supabase) {
      return;
    }

    // Fetch the most recent signal to get account_balance
    const fetchConfig = async () => {
      const { data } = await supabase
        .from('trading_signals')
        .select('account_balance, created_at')
        .order('created_at', { ascending: false })
        .limit(1)
        .maybeSingle();

      if (data?.account_balance != null) {
        setConfig({
          account_balance: data.account_balance,
          updated_at: data.created_at,
        });
      }
    };

    fetchConfig();

    // Subscribe to new signals to update account balance in real-time
    const channel = supabase
      .channel('pine-config-updates')
      .on(
        'postgres_changes',
        {
          event: 'INSERT',
          schema: 'public',
          table: 'trading_signals',
        },
        (payload: any) => {
          if (payload.new?.account_balance != null) {
            setConfig({
              account_balance: payload.new.account_balance,
              updated_at: payload.new.created_at,
            });
          }
        }
      )
      .subscribe();

    return () => {
      supabase.removeChannel(channel);
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
          (from TradingView)
        </span>
      </div>
    </div>
  );
}
