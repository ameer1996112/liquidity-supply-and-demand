'use client';

import { useEffect, useState } from 'react';
import { supabase } from '@/lib/supabase';
import { RealtimeChannel } from '@supabase/supabase-js';

type ConnectionState = 'loading' | 'online' | 'error';
type RealtimeState = 'SUBSCRIBED' | 'CLOSED' | 'CHANNEL_ERROR' | 'TIMED_OUT' | 'pending';

interface DebugInfo {
  envUrl: boolean;
  envKey: boolean;
  connectionState: ConnectionState;
  connectionError: string | null;
  realtimeState: RealtimeState;
  realtimeError: string | null;
}

export function DebugStatus() {
  const [debug, setDebug] = useState<DebugInfo>({
    envUrl: false,
    envKey: false,
    connectionState: 'loading',
    connectionError: null,
    realtimeState: 'pending',
    realtimeError: null,
  });

  useEffect(() => {
    // 1. Check environment variables
    const envUrl = !!process.env.NEXT_PUBLIC_SUPABASE_URL;
    const envKey = !!process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY;

    setDebug(prev => ({ ...prev, envUrl, envKey }));

    if (!supabase) {
      setDebug(prev => ({
        ...prev,
        connectionState: 'error',
        connectionError: 'Supabase client not initialized (missing credentials)',
      }));
      return;
    }

    // Capture non-null reference for closures
    const client = supabase;

    // 2. Test database connection
    const testConnection = async () => {
      try {
        const { error } = await client
          .from('trading_signals')
          .select('count', { count: 'exact', head: true });

        if (error) {
          setDebug(prev => ({
            ...prev,
            connectionState: 'error',
            connectionError: error.message,
          }));
        } else {
          setDebug(prev => ({
            ...prev,
            connectionState: 'online',
            connectionError: null,
          }));
        }
      } catch (err) {
        setDebug(prev => ({
          ...prev,
          connectionState: 'error',
          connectionError: err instanceof Error ? err.message : 'Unknown error',
        }));
      }
    };

    testConnection();

    // 3. Subscribe to realtime and monitor status
    const channel = client
      .channel('debug-status-channel')
      .on(
        'postgres_changes',
        { event: '*', schema: 'public', table: 'trading_signals' },
        () => {
          // Just monitoring subscription status
        }
      )
      .subscribe((status, err) => {
        setDebug(prev => ({
          ...prev,
          realtimeState: status as RealtimeState,
          realtimeError: err?.message || null,
        }));
      });

    // Cleanup
    return () => {
      client.removeChannel(channel);
    };
  }, []);

  const isOnline =
    debug.connectionState === 'online' && debug.realtimeState === 'SUBSCRIBED';

  const getErrorMessage = (): string | null => {
    if (debug.connectionError) return debug.connectionError;
    if (debug.realtimeError) return debug.realtimeError;
    if (!debug.envUrl) return 'NEXT_PUBLIC_SUPABASE_URL missing';
    if (!debug.envKey) return 'NEXT_PUBLIC_SUPABASE_ANON_KEY missing';
    if (debug.connectionState === 'loading') return 'Connecting...';
    if (debug.realtimeState === 'pending') return 'Realtime connecting...';
    if (debug.realtimeState === 'CLOSED') return 'Realtime channel closed';
    if (debug.realtimeState === 'CHANNEL_ERROR') return 'Realtime channel error';
    if (debug.realtimeState === 'TIMED_OUT') return 'Realtime timed out';
    return null;
  };

  const errorMessage = getErrorMessage();

  return (
    <div
      className={`fixed bottom-0 left-0 right-0 z-50 px-4 py-2 font-mono text-xs ${
        isOnline
          ? 'bg-emerald-950/90 border-t border-emerald-800/50 text-[var(--to-long)]'
          : 'bg-red-950/90 border-t border-red-800/50 text-[var(--to-short)]'
      }`}
    >
      <div className="max-w-screen-xl mx-auto flex items-center justify-between">
        {/* Status */}
        <div className="flex items-center gap-2">
          {isOnline ? (
            <span>✅ System Online</span>
          ) : (
            <span>❌ Disconnected: {errorMessage}</span>
          )}
        </div>

        {/* Debug Details */}
        <div className="flex items-center gap-4 text-[10px] opacity-70">
          <span>
            URL: {debug.envUrl ? '✓ Loaded' : '✗ Missing'}
          </span>
          <span>
            KEY: {debug.envKey ? '✓ Loaded' : '✗ Missing'}
          </span>
          <span>
            DB: {debug.connectionState}
          </span>
          <span>
            RT: {debug.realtimeState}
          </span>
        </div>
      </div>
    </div>
  );
}
