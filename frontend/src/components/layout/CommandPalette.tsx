'use client';

import { useEffect, useMemo, useState } from 'react';
import { usePathname, useRouter } from 'next/navigation';
import { Search, Command } from 'lucide-react';
import { cn } from '@/lib/utils';

type NavItem = {
  label: string;
  description: string;
  path: string;
  group: string;
};

const NAV_ITEMS: NavItem[] = [
  {
    label: 'Dashboard',
    description: 'Live command center',
    path: '/',
    group: 'Overview',
  },
  {
    label: 'Risk Monitor',
    description: 'Guard rails & limits',
    path: '/risk',
    group: 'Monitoring',
  },
  {
    label: 'Accounts',
    description: 'Multi-account manager',
    path: '/accounts',
    group: 'Portfolio',
  },
  {
    label: 'Execution Quality',
    description: 'Pipeline traces & TCA',
    path: '/execution-quality',
    group: 'Monitoring',
  },
  {
    label: 'Analytics',
    description: 'Performance analytics',
    path: '/analytics',
    group: 'Analytics',
  },
  {
    label: 'Backtest',
    description: 'Single-strategy backtest',
    path: '/backtest',
    group: 'Research',
  },
  {
    label: 'Backtests',
    description: 'Backtest runs library',
    path: '/backtests',
    group: 'Research',
  },
  {
    label: 'Strategies',
    description: 'Strategy Studio',
    path: '/strategies',
    group: 'Config',
  },
  {
    label: 'Rules',
    description: 'Risk & routing rules',
    path: '/rules',
    group: 'Config',
  },
  {
    label: 'Journal',
    description: 'Trade journal',
    path: '/journal',
    group: 'Review',
  },
  {
    label: 'Settings',
    description: 'System settings',
    path: '/settings',
    group: 'Config',
  },
];

function normalize(text: string): string {
  return text.toLowerCase();
}

export function CommandPalette() {
  const router = useRouter();
  const pathname = usePathname();

  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState('');
  const [activeIndex, setActiveIndex] = useState(0);

  // Keyboard shortcut: ⌘K / Ctrl+K
  useEffect(() => {
    const handler = (event: KeyboardEvent) => {
      const isModK =
        (event.metaKey || event.ctrlKey) && event.key.toLowerCase() === 'k';
      if (isModK) {
        event.preventDefault();
        setOpen((prev) => !prev);
        return;
      }

      if (event.key === 'Escape') {
        setOpen(false);
      }
    };

    window.addEventListener('keydown', handler);
    return () => window.removeEventListener('keydown', handler);
  }, []);

  useEffect(() => {
    if (!open) {
      setQuery('');
      setActiveIndex(0);
    }
  }, [open]);

  const filtered = useMemo(() => {
    const q = normalize(query.trim());
    if (!q) {
      return NAV_ITEMS;
    }

    return NAV_ITEMS.filter((item) => {
      const haystack = `${item.label} ${item.description} ${item.group} ${item.path}`;
      return normalize(haystack).includes(q);
    });
  }, [query]);

  const handleSelectNav = (item: NavItem) => {
    setOpen(false);
    if (item.path !== pathname) {
      router.push(item.path);
    }
  };

  const handleSubmit = () => {
    const raw = query.trim();

    // Quick search: signal_id (numeric, with or without # prefix)
    const numericCandidate = raw.replace(/[^\d]/g, '');
    if (numericCandidate && /^\d+$/.test(numericCandidate)) {
      const signalId = Number(numericCandidate);
      if (!Number.isNaN(signalId) && signalId > 0) {
        setOpen(false);
        router.push(`/execution-quality?signal_id=${signalId}`);
        return;
      }
    }



    // Fallback: first nav item
    const first = filtered[activeIndex] ?? filtered[0];
    if (first) {
      handleSelectNav(first);
    }
  };

  if (!open) {
    return null;
  }

  return (
    <div className='fixed inset-0 z-50 flex items-start justify-center bg-black/40 pt-16'>
      <div className='w-full max-w-xl rounded-xl border border-[var(--to-border)] bg-[var(--to-bg)] shadow-2xl'>
        {/* Input row */}
        <div className='flex items-center gap-2 border-b border-[var(--to-border)] px-3 py-2.5'>
          <div className='flex h-6 w-6 items-center justify-center rounded bg-[var(--to-surface)] text-[var(--to-text-dim)]'>
            <Command className='h-3.5 w-3.5' />
          </div>
          <input
            id='command-palette-search'
            autoFocus
            placeholder='Jump to page or search #signal / ticket…'
            value={query}
            onChange={(e) => {
              setQuery(e.target.value);
              setActiveIndex(0);
            }}
            onKeyDown={(e) => {
              if (e.key === 'ArrowDown') {
                e.preventDefault();
                setActiveIndex((prev) =>
                  prev + 1 >= filtered.length ? prev : prev + 1,
                );
              } else if (e.key === 'ArrowUp') {
                e.preventDefault();
                setActiveIndex((prev) => (prev - 1 < 0 ? 0 : prev - 1));
              } else if (e.key === 'Enter') {
                e.preventDefault();
                handleSubmit();
              }
            }}
            className='flex-1 bg-transparent text-sm text-[var(--to-text-primary)] outline-none placeholder:text-[var(--to-text-dim)]'
            style={{ fontFamily: 'var(--font-mono)' }}
          />
          <span
            className='hidden items-center gap-1 rounded border border-[var(--to-border)] bg-[var(--to-surface)] px-1.5 py-0.5 text-[10px] text-[var(--to-text-dim)] sm:inline-flex'
            style={{ fontFamily: 'var(--font-mono)' }}
          >
            ⌘K
          </span>
        </div>

        {/* Results */}
        <div className='max-h-[360px] overflow-y-auto py-1'>
          {filtered.length === 0 ? (
            <div className='flex items-center gap-2 px-3 py-3 text-xs text-[var(--to-text-dim)]'>
              <Search className='h-3.5 w-3.5' />
              <span>No matches. Try a different query.</span>
            </div>
          ) : (
            <ul className='space-y-0.5'>
              {filtered.map((item, index) => (
                <li key={item.path}>
                  <button
                    type='button'
                    onClick={() => handleSelectNav(item)}
                    className={cn(
                      'flex w-full items-center justify-between gap-2 px-3 py-1.5 text-left',
                      'text-[12px] transition-colors',
                      index === activeIndex
                        ? 'bg-[var(--to-surface-raised)] text-[var(--to-text-primary)]'
                        : 'text-[var(--to-text-secondary)] hover:bg-[var(--to-surface)]',
                    )}
                  >
                    <div className='flex flex-col'>
                      <span
                        className='font-medium'
                        style={{ fontFamily: 'var(--font-sans)' }}
                      >
                        {item.label}
                      </span>
                      <span
                        className='text-[10px] text-[var(--to-text-dim)]'
                        style={{ fontFamily: 'var(--font-mono)' }}
                      >
                        {item.description}
                      </span>
                    </div>
                    <div className='flex items-center gap-2'>
                      <span
                        className='rounded-full bg-[var(--to-surface)] px-2 py-0.5 text-[9px] uppercase tracking-[0.18em] text-[var(--to-text-dim)]'
                        style={{ fontFamily: 'var(--font-mono)' }}
                      >
                        {item.group}
                      </span>
                      <span
                        className='hidden text-[10px] text-[var(--to-text-dim)] sm:inline'
                        style={{ fontFamily: 'var(--font-mono)' }}
                      >
                        {item.path}
                      </span>
                    </div>
                  </button>
                </li>
              ))}
            </ul>
          )}
        </div>

        {/* Footer hint */}
        <div className='flex items-center justify-between border-t border-[var(--to-border)] px-3 py-1.5'>
          <span
            className='text-[9px] text-[var(--to-text-dim)]'
            style={{ fontFamily: 'var(--font-mono)' }}
          >
            Tip: type{' '}
            <span className='text-[var(--to-text-secondary)]'>#12345</span> to
            jump to a signal.
          </span>
        </div>
      </div>
    </div>
  );
}
