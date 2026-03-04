'use client';

import { useState, useRef, useEffect, useCallback } from 'react';
import { Sparkles, X, Send, RotateCcw, Brain } from 'lucide-react';
import { cn } from '@/lib/utils';
import { useQuery } from '@tanstack/react-query';
import { fetchSignals } from '@/lib/supabase';
import { queryCopilot, QUICK_ACTIONS, CopilotMessage } from './copilotEngine';
import { fetchCopilotAnswer, type CopilotHistoryMessage } from '@/lib/api';
import { TradingSignal, getPnl, getSymbol, getSide } from '@/types/trading';
import { format } from 'date-fns';
import { PnLText } from '@/components/ui/typography';

// ── Markdown-style text renderer ─────────────────────────────────────────────

function renderText(text: string) {
  const parts = text.split(/(\*\*[^*]+\*\*)/g);
  return parts.map((part, i) => {
    if (part.startsWith('**') && part.endsWith('**')) {
      return (
        <strong key={i} className='text-[var(--to-text-primary)] font-semibold'>
          {part.slice(2, -2)}
        </strong>
      );
    }
    return <span key={i}>{part}</span>;
  });
}

// ── Signal Mini Card ──────────────────────────────────────────────────────────

function SignalMiniCard({ signal }: { signal: TradingSignal }) {
  const pnl = getPnl(signal);
  const side = getSide(signal);

  return (
    <div className='flex items-center justify-between px-3 py-2 rounded-lg border border-[var(--to-border)] bg-[var(--to-surface-raised)] gap-3 text-[11px]'>
      <div className='flex items-center gap-2 min-w-0'>
        <span
          className='shrink-0 px-1.5 py-0.5 rounded font-bold text-[9px]'
          style={{
            backgroundColor: side === 'buy' ? '#0ecb8120' : '#f6465d20',
            color: side === 'buy' ? '#0ecb81' : '#f6465d',
          }}
        >
          {side.toUpperCase()}
        </span>
        <span className='font-mono font-semibold text-[var(--to-text-primary)] truncate'>
          {getSymbol(signal)}
        </span>
        <span className='text-[var(--to-text-dim)] shrink-0'>
          {format(new Date(signal.created_at), 'MMM dd')}
        </span>
      </div>
      <div className='shrink-0'>
        {pnl != null ? (
          <PnLText value={pnl} variant='currency' size='sm' />
        ) : (
          <span
            className='px-1.5 py-0.5 rounded text-[9px] font-mono font-semibold'
            style={{
              backgroundColor: '#3b82f620',
              color: '#3b82f6',
            }}
          >
            {(signal.status || '').toUpperCase().replace('_', ' ')}
          </span>
        )}
      </div>
    </div>
  );
}

// ── Response Data Renderer ────────────────────────────────────────────────────

function ResponseDataRenderer({
  data,
}: {
  data: NonNullable<CopilotMessage['data']>;
}) {
  if (data.type === 'stat-cards' && data.statCards) {
    return (
      <div className='grid grid-cols-2 gap-2 mt-3'>
        {data.statCards.map((card, i) => (
          <div
            key={i}
            className='flex flex-col gap-0.5 rounded-lg px-3 py-2.5 border border-[var(--to-border)] bg-[var(--to-surface-raised)]'
          >
            <span className='text-[10px] text-[var(--to-text-dim)]'>
              {card.label}
            </span>
            <span
              className='text-[15px] font-bold font-mono tabular-nums'
              style={{ color: card.color || 'var(--to-text-primary)' }}
            >
              {card.value}
            </span>
          </div>
        ))}
      </div>
    );
  }

  if (data.type === 'table' && data.tableRows) {
    return (
      <div className='mt-3 space-y-1.5'>
        {data.tableRows.map((row, i) => (
          <div
            key={i}
            className='flex items-center justify-between gap-3 px-3 py-2 rounded-lg border border-[var(--to-border)] bg-[var(--to-surface-raised)]'
          >
            <span className='text-[11px] text-[var(--to-text-secondary)] font-mono truncate'>
              {row.key}
            </span>
            <span
              className='text-[11px] font-mono font-semibold text-right shrink-0'
              style={{ color: row.color || 'var(--to-text-primary)' }}
            >
              {row.value}
            </span>
          </div>
        ))}
      </div>
    );
  }

  if (data.type === 'signal-list' && data.signals) {
    return (
      <div className='mt-3 space-y-1.5'>
        {data.signals.map((signal, i) => (
          <SignalMiniCard key={signal.id || i} signal={signal} />
        ))}
      </div>
    );
  }

  return null;
}

// ── Message Bubble ────────────────────────────────────────────────────────────

function MessageBubble({ message }: { message: CopilotMessage }) {
  const isUser = message.role === 'user';

  return (
    <div
      className={cn(
        'flex flex-col gap-1',
        isUser ? 'items-end' : 'items-start',
      )}
    >
      <div
        className={cn(
          'max-w-[85%] rounded-2xl px-4 py-2.5 text-[12px] leading-relaxed',
          isUser
            ? 'rounded-br-sm bg-[#3b82f6] text-white'
            : 'rounded-bl-sm bg-[var(--to-surface-raised)] border border-[var(--to-border)] text-[var(--to-text-secondary)]',
        )}
      >
        <div className='whitespace-pre-line'>{renderText(message.content)}</div>
        {!isUser && message.data && (
          <ResponseDataRenderer data={message.data} />
        )}
      </div>
      <span className='text-[10px] text-[var(--to-text-dim)] px-1 font-mono'>
        {format(message.timestamp, 'HH:mm')}
      </span>
    </div>
  );
}

// ── Typing Indicator ──────────────────────────────────────────────────────────

function TypingIndicator() {
  return (
    <div className='flex items-start'>
      <div className='rounded-2xl rounded-bl-sm bg-[var(--to-surface-raised)] border border-[var(--to-border)] px-4 py-2.5'>
        <div className='flex items-center gap-1'>
          {[0, 1, 2].map((i) => (
            <span
              key={i}
              className='inline-block w-1.5 h-1.5 rounded-full bg-[var(--to-text-dim)]'
              style={{
                animation: `bounce 1.2s infinite ${i * 0.2}s`,
              }}
            />
          ))}
        </div>
      </div>
    </div>
  );
}

// ── Main Component ────────────────────────────────────────────────────────────

interface AICopilotProps {
  open: boolean;
  onClose: () => void;
}

export function AICopilot({ open, onClose }: AICopilotProps) {
  const [messages, setMessages] = useState<CopilotMessage[]>([
    {
      role: 'assistant',
      content:
        '👋 Hi! I\'m your trading AI Copilot. Ask me anything about your trade history.\n\nTry: "Show my best setups" or "Why was the last trade rejected?"',
      timestamp: new Date(),
    },
  ]);
  const [input, setInput] = useState('');
  const [isThinking, setIsThinking] = useState(false);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  // Fetch all signals for query engine
  const { data: signals = [] } = useQuery({
    queryKey: ['copilot-signals'],
    queryFn: () => fetchSignals({ limit: 500 }),
    staleTime: 5 * 60 * 1000,
  });

  useEffect(() => {
    if (open) {
      setTimeout(() => inputRef.current?.focus(), 100);
    }
  }, [open]);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, isThinking]);

  const sendMessage = useCallback(
    async (query: string) => {
      if (!query.trim()) return;

      const userMsg: CopilotMessage = {
        role: 'user',
        content: query,
        timestamp: new Date(),
      };

      setMessages((prev) => [...prev, userMsg]);
      setInput('');
      setIsThinking(true);

      // Simulate brief "thinking" delay for UX
      await new Promise((r) => setTimeout(r, 600));

      const response = queryCopilot(query, signals as TradingSignal[]);
      const assistantMsg: CopilotMessage = {
        role: 'assistant',
        content: response.text,
        data: response.data,
        timestamp: new Date(),
      };

      setIsThinking(false);
      setMessages((prev) => [...prev, assistantMsg]);
    },
    [signals],
  );

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    sendMessage(input);
  };

  const handleClear = () => {
    setMessages([
      {
        role: 'assistant',
        content:
          '👋 Chat cleared. What would you like to know about your trades?',
        timestamp: new Date(),
      },
    ]);
  };

  if (!open) return null;

  return (
    <>
      {/* Backdrop */}
      <div
        className='fixed inset-0 z-40 bg-black/20 backdrop-blur-[1px]'
        onClick={onClose}
      />

      {/* Panel */}
      <div
        className='fixed right-0 top-0 bottom-0 z-50 flex flex-col'
        style={{
          width: 'min(420px, 100vw)',
          backgroundColor: 'var(--to-bg)',
          borderLeft: '1px solid var(--to-border)',
          boxShadow: '-20px 0 60px rgba(0,0,0,0.4)',
        }}
      >
        {/* Header */}
        <div
          className='flex items-center justify-between px-4 py-3.5 border-b border-[var(--to-border)] shrink-0'
          style={{
            background: 'linear-gradient(135deg, #1a1f2e 0%, #12161c 100%)',
          }}
        >
          <div className='flex items-center gap-2.5'>
            <div
              className='flex h-8 w-8 items-center justify-center rounded-lg'
              style={{
                background: 'linear-gradient(135deg, #6366f1 0%, #8b5cf6 100%)',
                boxShadow: '0 0 16px rgba(99,102,241,0.4)',
              }}
            >
              <Sparkles className='h-4 w-4 text-white' />
            </div>
            <div>
              <div className='text-[13px] font-semibold text-[var(--to-text-primary)]'>
                AI Copilot
              </div>
              <div className='text-[10px] text-[var(--to-text-dim)] font-mono'>
                {signals.length} signals loaded
              </div>
            </div>
          </div>
          <div className='flex items-center gap-1'>
            <button
              onClick={handleClear}
              className='flex h-7 w-7 items-center justify-center rounded-lg text-[var(--to-text-dim)] hover:bg-[var(--to-surface-raised)] hover:text-[var(--to-text-secondary)] transition-colors'
              title='Clear chat'
            >
              <RotateCcw className='h-3.5 w-3.5' />
            </button>
            <button
              onClick={onClose}
              className='flex h-7 w-7 items-center justify-center rounded-lg text-[var(--to-text-dim)] hover:bg-[var(--to-surface-raised)] hover:text-[var(--to-text-secondary)] transition-colors'
            >
              <X className='h-4 w-4' />
            </button>
          </div>
        </div>

        {/* Quick Actions */}
        <div className='px-4 py-2.5 border-b border-[var(--to-border)] shrink-0'>
          <div className='flex gap-1.5 overflow-x-auto scrollbar-none pb-0.5'>
            {QUICK_ACTIONS.map((action) => (
              <button
                key={action.query}
                onClick={() => sendMessage(action.query)}
                className='shrink-0 rounded-full border border-[var(--to-border)] bg-[var(--to-surface-raised)] px-2.5 py-1 text-[10px] text-[var(--to-text-secondary)] hover:border-[#6366f1]/50 hover:text-[var(--to-text-primary)] hover:bg-[#6366f1]/8 transition-all whitespace-nowrap'
              >
                {action.label}
              </button>
            ))}
          </div>
        </div>

        {/* Messages */}
        <div className='flex-1 overflow-y-auto px-4 py-4 space-y-4 scrollbar-thin'>
          {messages.map((msg, i) => (
            <MessageBubble key={i} message={msg} />
          ))}
          {isThinking && <TypingIndicator />}
          <div ref={messagesEndRef} />
        </div>

        {/* Input */}
        <div className='px-4 py-3.5 border-t border-[var(--to-border)] shrink-0'>
          <form onSubmit={handleSubmit} className='flex items-center gap-2'>
            <input
              ref={inputRef}
              value={input}
              onChange={(e) => setInput(e.target.value)}
              placeholder='Ask about your trades…'
              className='flex-1 rounded-xl border border-[var(--to-border)] bg-[var(--to-surface-raised)] px-3.5 py-2.5 text-[12px] text-[var(--to-text-primary)] placeholder:text-[var(--to-text-dim)] outline-none focus:border-[#6366f1]/50 transition-colors'
              style={{ fontFamily: 'var(--font-sans)' }}
              disabled={isThinking}
            />
            <button
              type='submit'
              disabled={!input.trim() || isThinking}
              className='flex h-9 w-9 shrink-0 items-center justify-center rounded-xl text-white transition-all disabled:opacity-40'
              style={{
                background: 'linear-gradient(135deg, #6366f1 0%, #8b5cf6 100%)',
                boxShadow: input.trim()
                  ? '0 0 12px rgba(99,102,241,0.4)'
                  : 'none',
              }}
            >
              <Send className='h-3.5 w-3.5' />
            </button>
          </form>
          <div className='mt-1.5 text-center'>
            <span className='text-[9px] text-[var(--to-text-dim)] font-mono'>
              Press{' '}
              <kbd className='px-1 rounded border border-[var(--to-border)]'>
                ⌘/
              </kbd>{' '}
              to toggle · Queries run locally over your trade data
            </span>
          </div>
        </div>
      </div>

      {/* Bounce keyframes */}
      <style>{`
        @keyframes bounce {
          0%, 60%, 100% { transform: translateY(0); opacity: 0.4; }
          30% { transform: translateY(-4px); opacity: 1; }
        }
      `}</style>
    </>
  );
}

// ── Trigger Button ────────────────────────────────────────────────────────────

export function AICopilotTrigger({ onClick }: { onClick: () => void }) {
  return (
    <button
      onClick={onClick}
      id='ai-copilot-trigger'
      className='flex items-center gap-1.5 rounded-lg border border-[var(--to-border)] px-2.5 py-1.5 text-[11px] text-[var(--to-text-secondary)] hover:border-[#6366f1]/50 hover:text-[var(--to-text-primary)] hover:bg-[#6366f1]/8 transition-all group'
      title='AI Copilot (⌘/)'
    >
      <Sparkles className='h-3.5 w-3.5 text-[#6366f1] group-hover:text-[#8b5cf6] transition-colors' />
      <span>Copilot</span>
      <kbd className='hidden sm:inline-flex items-center rounded border border-[var(--to-border)] bg-[var(--to-surface)] px-1 text-[9px] font-mono text-[var(--to-text-dim)]'>
        ⌘/
      </kbd>
    </button>
  );
}
