'use client';
import { useEffect, useState } from 'react';
import { supabase } from '@/lib/supabase';
import { cn } from '@/lib/utils';
import { Bot } from 'lucide-react';

interface FeedEvent {
  id: string;
  ticket_id: string;
  message: string;
  event_type: 'update' | 'move' | 'create' | 'close';
  created_at: string;
  agent_name?: string;
}

// Static timestamps avoid server/client hydration mismatch (React error #418)
const SEED_EVENTS: FeedEvent[] = [
  {
    id: 'seed-1',
    ticket_id: 'BUG-012',
    message:
      'began root-cause analysis. Identified race condition between council enrichment and signal persistence.',
    event_type: 'update',
    agent_name: 'Antigravity Agent',
    created_at: '2026-03-15T00:00:00.000Z',
  },
  {
    id: 'seed-2',
    ticket_id: 'BUG-011',
    message:
      'closed ticket. Fix: disabled Next.js force-cache on all Supabase fetches. Deployed & verified.',
    event_type: 'close',
    agent_name: 'Antigravity Agent',
    created_at: '2026-03-14T22:00:00.000Z',
  },
  {
    id: 'seed-3',
    ticket_id: 'BUG-010',
    message:
      'moved to In Progress. Investigating async worker pipeline for race conditions.',
    event_type: 'move',
    agent_name: 'Antigravity Agent',
    created_at: '2026-03-14T19:00:00.000Z',
  },
];

export function AgentFeed() {
  const [events, setEvents] = useState<FeedEvent[]>(SEED_EVENTS);

  useEffect(() => {
    if (!supabase) return;

    // Fetch last 10 events
    supabase
      .from('ticket_agent_events')
      .select('*')
      .order('created_at', { ascending: false })
      .limit(10)
      .then(({ data }) => {
        if (data && data.length > 0) {
          setEvents(data as FeedEvent[]);
        }
      });

    // Subscribe to new events via realtime
     
    const channel = (supabase as any)
      .channel('agent-feed')
      .on(
        'postgres_changes',
        { event: 'INSERT', schema: 'public', table: 'ticket_agent_events' },
        (payload: { new: FeedEvent }) => {
          setEvents((prev) => [payload.new, ...prev].slice(0, 20));
        }
      )
      .subscribe();

    return () => {
      supabase?.removeChannel(channel);
    };
  }, []);

  return (
    <div className='rounded-xl border border-[var(--to-border)] bg-[var(--to-surface)] overflow-hidden'>
      {/* Header */}
      <div className='flex items-center gap-2.5 border-b border-[var(--to-border)] px-4 py-3 bg-indigo-500/5'>
        <span className='h-2 w-2 rounded-full bg-emerald-400 animate-pulse shrink-0' />
        <Bot className='h-3.5 w-3.5 text-indigo-400' />
        <span className='text-[12px] font-semibold text-[var(--to-text-secondary)]'>
          AI Agent Activity Feed
        </span>
        <span
          className='ml-auto text-[10px] text-[var(--to-text-dim)]'
          style={{ fontFamily: 'var(--font-mono)' }}
        >
          Live
        </span>
      </div>

      {/* Events */}
      <div className='flex flex-col divide-y divide-[var(--to-border)]/50'>
        {events.length === 0 ? (
          <p className='px-4 py-6 text-center text-[11px] text-[var(--to-text-dim)]'>
            No agent activity yet.
          </p>
        ) : (
          events.map((ev) => (
            <div key={ev.id} className='flex gap-3 px-4 py-3'>
              <div
                className={cn(
                  'h-7 w-7 rounded-lg shrink-0 flex items-center justify-center text-xs',
                  ev.event_type === 'close'
                    ? 'bg-emerald-500/15'
                    : ev.event_type === 'move'
                      ? 'bg-yellow-500/15'
                      : 'bg-indigo-500/15'
                )}
              >
                {ev.event_type === 'close'
                  ? '✅'
                  : ev.event_type === 'move'
                    ? '↗️'
                    : '🤖'}
              </div>
              <div className='flex-1 min-w-0'>
                <p className='text-[11px] text-[var(--to-text-dim)] leading-relaxed'>
                  <strong className='text-[var(--to-text-secondary)]'>
                    {ev.agent_name ?? 'AI Agent'}
                  </strong>{' '}
                  <span className='text-indigo-400 font-semibold'>
                    [{ev.ticket_id}]
                  </span>{' '}
                  {ev.message}
                </p>
                <p
                  className='mt-0.5 text-[10px] text-[var(--to-text-dim)]'
                  style={{ fontFamily: 'var(--font-mono)' }}
                  suppressHydrationWarning
                >
                  {new Date(ev.created_at).toLocaleTimeString()}
                </p>
              </div>
            </div>
          ))
        )}
      </div>
    </div>
  );
}
