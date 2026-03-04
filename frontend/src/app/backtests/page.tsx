'use client';

import { useCallback, useEffect, useState } from 'react';
import { Play, RefreshCw, Loader2, Check, X } from 'lucide-react';
import { API_BASE_URL } from '@/lib/api';

interface BacktestJob {
  id: number;
  created_at: string;
  status: string;
  progress: number;
  start_time: string | null;
  end_time: string | null;
  config_snapshot: Record<string, unknown>;
  metrics_json: Record<string, unknown>;
  error_message: string | null;
}

export default function BacktestsPage() {
  const [jobs, setJobs] = useState<BacktestJob[]>([]);
  const [loading, setLoading] = useState(true);
  const [starting, setStarting] = useState(false);
  const [streamingId, setStreamingId] = useState<number | null>(null);
  const [streamLog, setStreamLog] = useState<string[]>([]);

  const loadJobs = useCallback(async () => {
    try {
      const r = await fetch(`${API_BASE_URL}/api/backtests`);
      const data = await r.json();
      setJobs(data.jobs || []);
    } catch (e) {
      console.error('Failed to load jobs:', e);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadJobs();
    const t = setInterval(loadJobs, 5000);
    return () => clearInterval(t);
  }, [loadJobs]);

  const handleStart = async () => {
    setStarting(true);
    try {
      const r = await fetch(`${API_BASE_URL}/api/backtests`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          symbol: '',
          start_date: '2025-01-01',
          end_date: '2026-12-31',
          initial_cash: 10000,
          daily_loss_limit: -500,
        }),
      });
      const data = await r.json();
      if (data.id) {
        setStreamingId(data.id);
        setStreamLog([]);
        const es = new EventSource(`${API_BASE_URL}/api/backtests/${data.id}/stream`);
        es.onmessage = (e) => {
          try {
            const ev = JSON.parse(e.data);
            setStreamLog((prev) => [...prev.slice(-50), `${ev.percent}%: ${ev.message}`]);
            if (ev.percent >= 100) es.close();
          } catch {}
        };
        es.onerror = () => es.close();
      }
      loadJobs();
    } catch (e) {
      console.error('Start failed:', e);
    } finally {
      setStarting(false);
    }
  };

  return (
    <div className='space-y-4'>
      <div className='flex items-center justify-between'>
        <div>
          <h1 className='page-title text-lg font-semibold'>Backtest Lab</h1>
          <p className='page-subtitle mt-0.5 text-xs'>
            AI pipeline replay with decision caching + SSE progress
          </p>
        </div>
        <div className='flex gap-2'>
          <button
            onClick={loadJobs}
            className='flex items-center gap-1.5 px-3 py-1.5 rounded bg-slate-800 text-slate-300 hover:bg-slate-700 text-sm font-mono'
          >
            <RefreshCw className='w-4 h-4' />
            Refresh
          </button>
          <button
            onClick={handleStart}
            disabled={starting}
            className='flex items-center gap-1.5 px-4 py-1.5 rounded bg-emerald-600 text-white hover:bg-emerald-500 disabled:opacity-50 text-sm font-mono'
          >
            {starting ? <Loader2 className='w-4 h-4 animate-spin' /> : <Play className='w-4 h-4' />}
            Start Backtest
          </button>
        </div>
      </div>

      {streamingId && streamLog.length > 0 && (
        <div className='tv-card p-4'>
          <div className='text-[11px] text-slate-500 font-mono mb-2'>Stream #{streamingId}</div>
          <div className='max-h-32 overflow-y-auto font-mono text-xs text-slate-300 space-y-0.5'>
            {streamLog.map((line, i) => (
              <div key={i}>{line}</div>
            ))}
          </div>
        </div>
      )}

      <div className='tv-card overflow-hidden'>
        <div className='px-4 py-3 border-b border-slate-800'>
          <span className='font-mono text-xs text-slate-500 uppercase tracking-wider'>Jobs</span>
        </div>
        {loading ? (
          <div className='p-8 flex justify-center'>
            <Loader2 className='w-6 h-6 text-slate-500 animate-spin' />
          </div>
        ) : jobs.length === 0 ? (
          <div className='p-8 text-center text-slate-500'>
            No backtest jobs yet. Click Start Backtest to run one.
          </div>
        ) : (
          <div className='divide-y divide-slate-800'>
            {jobs.map((job) => (
              <div
                key={job.id}
                className='px-4 py-3 flex items-center justify-between gap-4 hover:bg-slate-800/30'
              >
                <div className='flex items-center gap-3'>
                  <span className='font-mono text-sm text-slate-400'>#{job.id}</span>
                  <span
                    className={`inline-flex items-center gap-1 px-2 py-0.5 rounded text-[10px] font-mono ${
                      job.status === 'completed'
                        ? 'bg-emerald-500/20 text-emerald-400'
                        : job.status === 'failed'
                        ? 'bg-rose-500/20 text-rose-400'
                        : job.status === 'running'
                        ? 'bg-amber-500/20 text-amber-400'
                        : 'bg-slate-600/30 text-slate-400'
                    }`}
                  >
                    {job.status === 'completed' && <Check className='w-3 h-3' />}
                    {job.status === 'failed' && <X className='w-3 h-3' />}
                    {job.status}
                  </span>
                  {job.status === 'running' && (
                    <span className='text-xs text-slate-500'>{job.progress}%</span>
                  )}
                </div>
                <div className='text-xs text-slate-500'>
                  {new Date(job.created_at).toLocaleString()}
                </div>
                {job.status === 'completed' && job.metrics_json && (
                  <div className='flex gap-4 text-[11px] font-mono'>
                    <span className='text-slate-400'>
                      WR: {(job.metrics_json as Record<string, number | string>).win_rate ?? '—'}%
                    </span>
                    <span className='text-slate-400'>
                      Trades: {(job.metrics_json as Record<string, number | string>).total_trades ?? '—'}
                    </span>
                    <span className='text-slate-400'>
                      MaxDD: {(job.metrics_json as Record<string, number | string>).max_drawdown_pct ?? '—'}%
                    </span>
                    <span className='text-slate-400'>
                      Avg R: {(job.metrics_json as Record<string, number | string>).avg_r ?? '—'}
                    </span>
                  </div>
                )}
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
