'use client';

import { useEffect, useState } from 'react';
import { Keyboard, X } from 'lucide-react';
import { cn } from '@/lib/utils';

interface Shortcut {
  keys: string[];
  description: string;
  category: string;
}

const SHORTCUTS: Shortcut[] = [
  // Navigation
  {
    keys: ['⌘', 'K'],
    description: 'Open command palette',
    category: 'Navigation',
  },
  {
    keys: ['⌘', '/'],
    description: 'Toggle AI Copilot',
    category: 'Navigation',
  },
  {
    keys: ['?'],
    description: 'Show keyboard shortcuts',
    category: 'Navigation',
  },
  // Dashboard
  { keys: ['G', 'D'], description: 'Go to Dashboard', category: 'Navigation' },
  { keys: ['G', 'P'], description: 'Go to Positions', category: 'Navigation' },
  { keys: ['G', 'A'], description: 'Go to Analytics', category: 'Navigation' },
  { keys: ['G', 'J'], description: 'Go to Journal', category: 'Navigation' },
  {
    keys: ['G', 'R'],
    description: 'Go to Risk Monitor',
    category: 'Navigation',
  },
  // Actions
  { keys: ['Esc'], description: 'Close modal / panel', category: 'Actions' },
  { keys: ['↑', '↓'], description: 'Navigate list items', category: 'Actions' },
  { keys: ['Enter'], description: 'Select / confirm', category: 'Actions' },
];

const CATEGORIES = [...new Set(SHORTCUTS.map((s) => s.category))];

function KeyBadge({ k }: { k: string }) {
  return (
    <kbd
      className='inline-flex items-center justify-center rounded border border-[var(--to-border)] bg-[var(--to-surface-raised)] px-1.5 py-0.5 text-[10px] font-semibold text-[var(--to-text-secondary)] shadow-sm min-w-[22px]'
      style={{ fontFamily: 'var(--font-mono)' }}
    >
      {k}
    </kbd>
  );
}

export function KeyboardShortcutsModal() {
  const [open, setOpen] = useState(false);

  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      // '?' key — only when not in an input
      if (
        e.key === '?' &&
        !['INPUT', 'TEXTAREA'].includes((e.target as HTMLElement)?.tagName)
      ) {
        e.preventDefault();
        setOpen((prev) => !prev);
      }
      if (e.key === 'Escape') setOpen(false);
    };
    window.addEventListener('keydown', handler);
    return () => window.removeEventListener('keydown', handler);
  }, []);

  if (!open) return null;

  return (
    <div
      className='fixed inset-0 z-[200] flex items-center justify-center p-4'
      onClick={() => setOpen(false)}
    >
      {/* Backdrop */}
      <div className='absolute inset-0 bg-black/60 backdrop-blur-sm' />

      {/* Modal */}
      <div
        className='relative z-10 w-full max-w-lg rounded-2xl border border-[var(--to-border)] bg-[#0d1117]/98 shadow-2xl backdrop-blur-xl animate-fade-in-up'
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <div className='flex items-center justify-between border-b border-[var(--to-border)] px-5 py-4'>
          <div className='flex items-center gap-2.5'>
            <Keyboard className='h-4 w-4 text-[var(--to-accent-blue)]' />
            <span
              className='text-[13px] font-semibold text-[var(--to-text-primary)]'
              style={{ fontFamily: 'var(--font-sans)' }}
            >
              Keyboard Shortcuts
            </span>
          </div>
          <button
            onClick={() => setOpen(false)}
            className='flex h-7 w-7 items-center justify-center rounded-lg text-[var(--to-text-dim)] hover:bg-[var(--to-surface-raised)] hover:text-[var(--to-text-primary)] transition-colors'
          >
            <X className='h-3.5 w-3.5' />
          </button>
        </div>

        {/* Content */}
        <div className='max-h-[60vh] overflow-y-auto p-5 space-y-5 scrollbar-thin'>
          {CATEGORIES.map((category) => (
            <div key={category}>
              <p
                className='mb-2.5 text-[9px] font-bold uppercase tracking-[0.18em] text-[var(--to-text-dim)]'
                style={{ fontFamily: 'var(--font-mono)' }}
              >
                {category}
              </p>
              <div className='space-y-1.5'>
                {SHORTCUTS.filter((s) => s.category === category).map(
                  (shortcut) => (
                    <div
                      key={shortcut.description}
                      className='flex items-center justify-between rounded-lg px-3 py-2 hover:bg-[var(--to-surface-raised)] transition-colors'
                    >
                      <span
                        className='text-[12px] text-[var(--to-text-secondary)]'
                        style={{ fontFamily: 'var(--font-sans)' }}
                      >
                        {shortcut.description}
                      </span>
                      <div className='flex items-center gap-1'>
                        {shortcut.keys.map((k, i) => (
                          <span key={i} className='flex items-center gap-1'>
                            <KeyBadge k={k} />
                            {i < shortcut.keys.length - 1 && (
                              <span className='text-[9px] text-[var(--to-text-dim)]'>
                                +
                              </span>
                            )}
                          </span>
                        ))}
                      </div>
                    </div>
                  )
                )}
              </div>
            </div>
          ))}
        </div>

        {/* Footer */}
        <div className='border-t border-[var(--to-border)] px-5 py-3'>
          <p
            className='text-center text-[10px] text-[var(--to-text-dim)]'
            style={{ fontFamily: 'var(--font-mono)' }}
          >
            Press <KeyBadge k='?' /> anywhere to toggle this panel
          </p>
        </div>
      </div>
    </div>
  );
}
