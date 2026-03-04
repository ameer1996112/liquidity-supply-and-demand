'use client';

import { useEffect, useRef, useState, useCallback } from 'react';
import { Terminal, Pause, Play, Trash2, ChevronDown } from 'lucide-react';
import { cn } from '@/lib/utils';

export interface LogEntry {
  id: string;
  timestamp: string;
  level: 'info' | 'warn' | 'error' | 'success' | 'debug';
  message: string;
  source?: string;
}

interface LiveLogProps {
  entries: LogEntry[];
  maxLines?: number;
  title?: string;
  className?: string;
  onClear?: () => void;
}

const LEVEL_STYLES: Record<LogEntry['level'], { prefix: string; color: string }> = {
  info: { prefix: 'INF', color: 'text-[var(--to-accent-blue)]' },
  warn: { prefix: 'WRN', color: 'text-[var(--to-warning)]' },
  error: { prefix: 'ERR', color: 'text-[var(--to-short)]' },
  success: { prefix: 'OK ', color: 'text-[var(--to-long)]' },
  debug: { prefix: 'DBG', color: 'text-[var(--to-text-dim)]' },
};

function formatTimestamp(iso: string): string {
  const d = new Date(iso);
  return d.toLocaleTimeString('en-GB', {
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
    hour12: false,
  });
}

export function LiveLog({
  entries,
  maxLines = 200,
  title = 'Live Log',
  className,
  onClear,
}: LiveLogProps) {
  const scrollRef = useRef<HTMLDivElement>(null);
  const [paused, setPaused] = useState(false);
  const [autoScroll, setAutoScroll] = useState(true);

  const visibleEntries = entries.slice(-maxLines);

  useEffect(() => {
    if (!paused && autoScroll && scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [visibleEntries.length, paused, autoScroll]);

  const handleScroll = useCallback(() => {
    if (!scrollRef.current) return;
    const { scrollTop, scrollHeight, clientHeight } = scrollRef.current;
    const atBottom = scrollHeight - scrollTop - clientHeight < 40;
    setAutoScroll(atBottom);
  }, []);

  const scrollToBottom = useCallback(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
      setAutoScroll(true);
    }
  }, []);

  return (
    <div
      className={cn(
        'flex flex-col overflow-hidden rounded border border-[var(--to-border)] bg-[#0a0d10]',
        className,
      )}
    >
      {/* Header */}
      <div className='flex items-center justify-between border-b border-[var(--to-border)] px-2.5 py-1.5'>
        <div className='flex items-center gap-2'>
          <Terminal className='h-3.5 w-3.5 text-[var(--to-long)]' />
          <span
            className='text-[10px] font-semibold uppercase tracking-wider text-[var(--to-text-secondary)]'
            style={{ fontFamily: 'var(--font-mono)' }}
          >
            {title}
          </span>
          <span
            className='text-[9px] tabular-nums text-[var(--to-text-dim)]'
            style={{ fontFamily: 'var(--font-mono)' }}
          >
            {visibleEntries.length} lines
          </span>
        </div>
        <div className='flex items-center gap-1'>
          <button
            onClick={() => setPaused((p) => !p)}
            className='rounded p-1 text-[var(--to-text-dim)] transition-colors hover:bg-[var(--to-surface-raised)] hover:text-[var(--to-text-secondary)]'
            title={paused ? 'Resume' : 'Pause'}
          >
            {paused ? <Play className='h-3 w-3' /> : <Pause className='h-3 w-3' />}
          </button>
          {onClear && (
            <button
              onClick={onClear}
              className='rounded p-1 text-[var(--to-text-dim)] transition-colors hover:bg-[var(--to-surface-raised)] hover:text-[var(--to-text-secondary)]'
              title='Clear log'
            >
              <Trash2 className='h-3 w-3' />
            </button>
          )}
        </div>
      </div>

      {/* Log output */}
      <div
        ref={scrollRef}
        onScroll={handleScroll}
        className='flex-1 overflow-x-auto overflow-y-auto px-2.5 py-1.5 scrollbar-thin'
        style={{ fontFamily: 'var(--font-mono)', fontSize: '11px', lineHeight: '1.6' }}
      >
        {visibleEntries.length === 0 ? (
          <div className='flex h-full items-center justify-center'>
            <span className='text-[10px] text-[var(--to-text-dim)]'>
              Waiting for events...
            </span>
          </div>
        ) : (
          visibleEntries.map((entry) => {
            const style = LEVEL_STYLES[entry.level];
            return (
              <div key={entry.id} className='flex gap-2'>
                <span className='shrink-0 tabular-nums text-[var(--to-text-dim)] whitespace-nowrap'>
                  {formatTimestamp(entry.timestamp)}
                </span>
                <span className={cn('shrink-0 font-bold whitespace-nowrap', style.color)}>
                  [{style.prefix}]
                </span>
                {entry.source && (
                  <span className='shrink-0 whitespace-nowrap text-[var(--to-accent-blue)]/60'>
                    {entry.source}
                  </span>
                )}
                <span
                  className='min-w-0 shrink-0 break-words text-[var(--to-text-secondary)]'
                  title={entry.message}
                >
                  {entry.message}
                </span>
              </div>
            );
          })
        )}
      </div>

      {/* Scroll-to-bottom indicator */}
      {!autoScroll && (
        <button
          onClick={scrollToBottom}
          className='flex items-center justify-center gap-1 border-t border-[var(--to-border)] bg-[var(--to-surface)] py-1 text-[9px] text-[var(--to-text-dim)] transition-colors hover:text-[var(--to-text-secondary)]'
          style={{ fontFamily: 'var(--font-mono)' }}
        >
          <ChevronDown className='h-3 w-3' />
          Scroll to latest
        </button>
      )}
    </div>
  );
}
