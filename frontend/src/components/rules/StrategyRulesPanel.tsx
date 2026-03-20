'use client';

import { useEffect, useState, useCallback } from 'react';
import { cn } from '@/lib/utils';
import { supabase } from '@/lib/supabase';

// Untyped accessor for tables not in the Database generic
 
const db = supabase as any;
import { getRulesStrategyUrl } from '@/lib/api';
import type { StrategyRule } from '@/types/rules';
import { Badge } from '@/components/ui/badge';
import { Trash2, Plus, Loader2, BookOpen, Send } from 'lucide-react';

const TIMEFRAME_OPTIONS = ['5m', '15m', '1h', '4h', '1d'] as const;

export function StrategyRulesPanel() {
  const [rules, setRules] = useState<StrategyRule[]>([]);
  const [loading, setLoading] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const [showForm, setShowForm] = useState(false);
  const [content, setContent] = useState('');
  const [timeframe, setTimeframe] = useState<string>('5m');
  const [error, setError] = useState('');

  const fetchRules = useCallback(async () => {
    if (!supabase) return;
    setLoading(true);
    setError('');
    try {
      const { data, error: err } = await db
        .from('documents')
        .select('id, content, metadata')
        .order('id', { ascending: false });
      if (err) throw err;
      setRules((data as StrategyRule[]) || []);
    } catch (e: unknown) {
      setError(
        e instanceof Error ? e.message : 'Failed to load strategy rules',
      );
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchRules();
  }, [fetchRules]);

  const addRule = async () => {
    const trimmed = content.trim();
    if (!trimmed) return;
    setSubmitting(true);
    setError('');
    try {
      const url = getRulesStrategyUrl();
      if (!url) throw new Error('Backend API URL not configured');
      const res = await fetch(url, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ content: trimmed, timeframe }),
      });
      if (!res.ok) {
        const body = await res.json().catch(() => ({}));
        throw new Error(body.detail || `HTTP ${res.status}`);
      }
      setContent('');
      setShowForm(false);
      await fetchRules();
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : 'Failed to add rule');
    } finally {
      setSubmitting(false);
    }
  };

  const deleteRule = async (id: string) => {
    if (!confirm('Delete this strategy rule?')) return;
    setError('');
    try {
      const url = getRulesStrategyUrl();
      if (!url) throw new Error('Backend API URL not configured');
      const res = await fetch(`${url}/${id}`, { method: 'DELETE' });
      if (!res.ok) {
        const body = await res.json().catch(() => ({}));
        throw new Error(body.detail || `HTTP ${res.status}`);
      }
      await fetchRules();
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : 'Failed to delete rule');
    }
  };

  if (!supabase) {
    return (
      <div className='glow-card p-6 text-center text-[var(--to-text-dim)] text-sm'>
        Supabase not configured. Set environment variables to manage rules.
      </div>
    );
  }

  return (
    <div className='space-y-4'>
      {error && (
        <div className='bg-[var(--to-short)]/10 border border-[var(--to-short)]/30 rounded-lg px-4 py-2 text-[var(--to-short)] text-xs font-mono'>
          {error}
        </div>
      )}

      <div className='flex items-center justify-between'>
        <div className='flex items-center gap-2'>
          <span className='text-xs text-[var(--to-text-dim)] font-mono uppercase tracking-wider'>
            RAG Strategy Knowledge Base
          </span>
          <Badge variant='secondary' className='text-[10px]'>
            {rules.length} rules
          </Badge>
        </div>
        <button
          onClick={() => setShowForm(!showForm)}
          className={cn(
            'flex items-center gap-1.5 px-3 py-1.5 rounded text-xs font-mono',
            'bg-[var(--to-long)]/10 text-[var(--to-long)] hover:bg-[var(--to-long)]/20 transition-colors',
          )}
        >
          <Plus className='w-3.5 h-3.5' />
          Add Rule
        </button>
      </div>

      {showForm && (
        <div className='glow-card p-4 space-y-3'>
          <div className='flex items-center gap-2'>
            <BookOpen className='w-4 h-4 text-[var(--to-text-dim)]' />
            <span className='text-xs font-mono text-[var(--to-text-dim)] uppercase tracking-wider'>
              New Strategy Rule
            </span>
          </div>
          <textarea
            id='strategy-rule-content'
            value={content}
            onChange={(e) => setContent(e.target.value)}
            placeholder="Enter strategy rule text... (e.g. 'Only take demand zone entries when liquidity has been swept below the zone within the last 5 candles')"
            rows={4}
            className={cn(
              'w-full bg-[#1e222d] border border-[#2a2e39] rounded-lg px-3 py-2',
              'text-xs font-mono text-[var(--to-text-primary)] placeholder:text-[var(--to-text-dim)]',
              'focus:outline-none focus:border-emerald-500 resize-y',
            )}
          />
          <div className='flex items-center justify-between'>
            <div className='flex items-center gap-2'>
              <span className='text-[10px] text-[var(--to-text-dim)] font-mono uppercase'>
                Timeframe:
              </span>
              <div className='flex gap-1'>
                {TIMEFRAME_OPTIONS.map((tf) => (
                  <button
                    key={tf}
                    onClick={() => setTimeframe(tf)}
                    className={cn(
                      'px-2 py-0.5 rounded text-[10px] font-mono transition-colors',
                      timeframe === tf
                        ? 'bg-[var(--to-long)]/20 text-[var(--to-long)] border border-[var(--to-long)]/30'
                        : 'bg-[#1e222d] text-[var(--to-text-dim)] border border-[#2a2e39] hover:text-[var(--to-text-secondary)]',
                    )}
                  >
                    {tf}
                  </button>
                ))}
              </div>
            </div>
            <div className='flex items-center gap-2'>
              <button
                onClick={() => {
                  setShowForm(false);
                  setContent('');
                }}
                className='px-3 py-1.5 rounded text-xs font-mono text-[var(--to-text-dim)] hover:text-[var(--to-text-secondary)] transition-colors'
              >
                Cancel
              </button>
              <button
                onClick={addRule}
                disabled={submitting || !content.trim()}
                className={cn(
                  'flex items-center gap-1.5 px-3 py-1.5 rounded text-xs font-mono',
                  'bg-emerald-500 text-white hover:bg-emerald-600 transition-colors',
                  'disabled:opacity-50 disabled:cursor-not-allowed',
                )}
              >
                {submitting ? (
                  <Loader2 className='w-3.5 h-3.5 animate-spin' />
                ) : (
                  <Send className='w-3.5 h-3.5' />
                )}
                Submit
              </button>
            </div>
          </div>
        </div>
      )}

      {loading ? (
        <div className='flex items-center justify-center py-12'>
          <Loader2 className='w-5 h-5 animate-spin text-[var(--to-text-dim)]' />
        </div>
      ) : rules.length === 0 ? (
        <div className='glow-card p-8 text-center'>
          <BookOpen className='w-8 h-8 text-[var(--to-text-dim)] mx-auto mb-3' />
          <p className='text-[var(--to-text-dim)] text-sm'>
            No strategy rules in the knowledge base.
          </p>
          <p className='text-[var(--to-text-dim)] text-xs mt-1'>
            Add rules that the AI will use when evaluating trade signals.
          </p>
        </div>
      ) : (
        <div className='space-y-2'>
          {rules.map((rule) => (
            <div
              key={rule.id}
              className='glow-card px-4 py-3 group hover:border-[#3a3e49] transition-colors'
            >
              <div className='flex items-start justify-between gap-3'>
                <div className='flex-1 min-w-0'>
                  <p className='text-xs text-[var(--to-text-secondary)] font-mono leading-relaxed whitespace-pre-wrap'>
                    {rule.content}
                  </p>
                  <div className='flex items-center gap-2 mt-2'>
                    {rule.metadata &&
                      Object.entries(rule.metadata).map(([key, value]) => (
                        <Badge
                          key={key}
                          variant='secondary'
                          className='text-[9px] font-mono'
                        >
                          {key}: {value}
                        </Badge>
                      ))}
                    <span className='text-[9px] text-[var(--to-text-dim)] font-mono'>
                      ID: {rule.id.slice(0, 8)}
                    </span>
                  </div>
                </div>
                <button
                  onClick={() => deleteRule(rule.id)}
                  className='p-1 text-[var(--to-text-dim)] hover:text-[var(--to-short)] transition-colors opacity-0 group-hover:opacity-100'
                >
                  <Trash2 className='w-3.5 h-3.5' />
                </button>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
