'use client';

import { useState, useRef, useEffect, useCallback } from 'react';
import {
  Sparkles,
  X,
  Send,
  RotateCcw,
  TrendingUp,
  BarChart2,
  Calendar,
  Award,
  AlertCircle,
  Zap,
} from 'lucide-react';
import { cn } from '@/lib/utils';
import { useQuery } from '@tanstack/react-query';
import { fetchSignals } from '@/lib/supabase';
import { queryCopilot, QUICK_ACTIONS, CopilotMessage } from './copilotEngine';
import { TradingSignal, getPnl, getSymbol, getSide } from '@/types/trading';
import { format } from 'date-fns';
import { PnLText } from '@/components/ui/typography';

// ── Suggested follow-ups map ──────────────────────────────────────────────────

const FOLLOW_UP_MAP: Record<string, string[]> = {
  pnl_summary: [
    'Win rate by symbol',
    'Show my best trades',
    'Show my Sharpe ratio',
  ],
  daily_summary: [
    'Win rate by day of week',
    'Show my worst day',
    'Show my best setups',
  ],
  best_setups: [
    'Show my worst trades',
    'Win rate by symbol',
    'How did I do today?',
  ],
  worst_setups: [
    'Show my best trades',
    'Win rate by session',
    'Show total PnL',
  ],
  win_rate_by_symbol: [
    'Win rate by session',
    'Win rate by day of week',
    'Show total PnL',
  ],
  win_rate_by_session: [
    'Win rate by day of week',
    'Win rate by symbol',
    'Show my best setups',
  ],
  win_rate_by_day: [
    'Win rate by session',
    'Show my worst day',
    'Show total PnL',
  ],
  rejection_reason: [
    'Show recent trades',
    'Show my best setups',
    'How did I do today?',
  ],
  symbol_query: ['Win rate by symbol', 'Show my best trades', 'Show total PnL'],
  sharpe: ['Show total PnL', 'Win rate by symbol', 'Show my best setups'],
  recent_trades: [
    'Show my best setups',
    'Win rate by symbol',
    'How did I do today?',
  ],
  count_trades: ['Show total PnL', 'Show my best setups', 'Win rate by symbol'],
  best_day: ['Show my worst day', 'Win rate by day of week', 'Show total PnL'],
  worst_day: ['Show my best day', 'Win rate by day of week', 'Show total PnL'],
  unknown: ['Show my total PnL', 'Show my best setups', 'Win rate by symbol'],
};

function getFollowUps(query: string): string[] {
  const q = query.toLowerCase();
  if (q.match(/reject|filter|block/)) return FOLLOW_UP_MAP.rejection_reason;
  if (q.match(/best setup|top setup|best trade/))
    return FOLLOW_UP_MAP.best_setups;
  if (q.match(/worst setup|worst trade/)) return FOLLOW_UP_MAP.worst_setups;
  if (q.match(/by symbol|per symbol/)) return FOLLOW_UP_MAP.win_rate_by_symbol;
  if (q.match(/by session|per session/))
    return FOLLOW_UP_MAP.win_rate_by_session;
  if (q.match(/by day|per day|day of week/))
    return FOLLOW_UP_MAP.win_rate_by_day;
  if (q.match(/pnl|profit|loss|total/)) return FOLLOW_UP_MAP.pnl_summary;
  if (q.match(/today|this week|summary/)) return FOLLOW_UP_MAP.daily_summary;
  if (q.match(/sharpe|sortino|ratio/)) return FOLLOW_UP_MAP.sharpe;
  if (q.match(/recent|last \d+ trade|latest/))
    return FOLLOW_UP_MAP.recent_trades;
  if (q.match(/how many|count/)) return FOLLOW_UP_MAP.count_trades;
  if (q.match(/best day/)) return FOLLOW_UP_MAP.best_day;
  if (q.match(/worst day/)) return FOLLOW_UP_MAP.worst_day;
  return FOLLOW_UP_MAP.unknown;
}

// ── Markdown renderer ─────────────────────────────────────────────────────────

function renderText(text: string) {
  return text.split(/(\*\*[^*]+\*\*)/g).map((part, i) =>
    part.startsWith('**') && part.endsWith('**') ? (
      <strong key={i} className='text-[var(--to-text-primary)] font-semibold'>
        {part.slice(2, -2)}
      </strong>
    ) : (
      <span key={i}>{part}</span>
    )
  );
}

// ── Signal Mini Card ──────────────────────────────────────────────────────────

function SignalMiniCard({ signal }: { signal: TradingSignal }) {
  const pnl = getPnl(signal);
  const side = getSide(signal);
  return (
    <div className='flex items-center justify-between px-3 py-2 rounded-lg border border-[var(--to-border)] bg-[var(--to-surface)] gap-3 text-[11px]'>
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
            style={{ backgroundColor: '#3b82f620', color: '#3b82f6' }}
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
      <div className='grid grid-cols-2 gap-1.5 mt-3'>
        {data.statCards.map((card, i) => (
          <div
            key={i}
            className='flex flex-col gap-0.5 rounded-lg overflow-hidden border border-[var(--to-border)] bg-[var(--to-surface)]'
          >
            <div
              className='h-0.5 w-full'
              style={{ backgroundColor: card.color || '#848e9c' }}
            />
            <div className='px-2.5 py-2'>
              <span className='text-[9px] text-[var(--to-text-dim)] uppercase tracking-wide font-mono'>
                {card.label}
              </span>
              <div
                className='text-[15px] font-bold font-mono tabular-nums mt-0.5'
                style={{ color: card.color || 'var(--to-text-primary)' }}
              >
                {card.value}
              </div>
            </div>
          </div>
        ))}
      </div>
    );
  }

  if (data.type === 'table' && data.tableRows) {
    return (
      <div className='mt-3 space-y-1'>
        {data.tableRows.map((row, i) => (
          <div
            key={i}
            className='flex items-center justify-between gap-3 px-3 py-2 rounded-lg border border-[var(--to-border)]'
            style={{
              backgroundColor:
                i % 2 === 0 ? 'var(--to-surface)' : 'var(--to-surface-raised)',
            }}
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

interface ExtendedMessage extends CopilotMessage {
  followUps?: string[];
}

function MessageBubble({
  message,
  onFollowUp,
}: {
  message: ExtendedMessage;
  onFollowUp: (q: string) => void;
}) {
  const isUser = message.role === 'user';
  return (
    <div
      className={cn(
        'flex flex-col gap-1 animate-fade-in-up',
        isUser ? 'items-end' : 'items-start'
      )}
    >
      {!isUser && (
        <div className='flex items-center gap-1.5 px-1'>
          <div
            className='flex h-5 w-5 items-center justify-center rounded-md shrink-0'
            style={{
              background: 'linear-gradient(135deg,#6366f1 0%,#8b5cf6 100%)',
            }}
          >
            <Sparkles className='h-2.5 w-2.5 text-white' />
          </div>
          <span className='text-[9px] font-mono text-[var(--to-text-dim)]'>
            AI Copilot
          </span>
        </div>
      )}
      <div
        className={cn(
          'max-w-[88%] min-w-0 overflow-hidden rounded-2xl px-4 py-2.5 text-[12px] leading-relaxed',
          isUser
            ? 'rounded-br-sm bg-gradient-to-br from-[#3b82f6] to-[#2563eb] text-white shadow-[0_4px_16px_rgba(59,130,246,0.3)]'
            : 'rounded-bl-sm bg-[var(--to-surface-raised)] border border-[var(--to-border)] text-[var(--to-text-secondary)]'
        )}
      >
        <div className='whitespace-pre-line'>{renderText(message.content)}</div>
        {!isUser && message.data && (
          <ResponseDataRenderer data={message.data} />
        )}
      </div>

      {/* Suggested follow-ups */}
      {!isUser && message.followUps && message.followUps.length > 0 && (
        <div className='flex flex-wrap gap-1 px-1 mt-1 max-w-[88%]'>
          {message.followUps.map((fu, i) => (
            <button
              key={i}
              onClick={() => onFollowUp(fu)}
              className='rounded-full border border-[var(--to-border)] bg-[var(--to-surface)] px-2.5 py-1 text-[10px] text-[var(--to-text-dim)] hover:border-[#6366f1]/50 hover:text-[var(--to-text-primary)] hover:bg-[#6366f1]/8 transition-all whitespace-nowrap'
            >
              {fu}
            </button>
          ))}
        </div>
      )}

      <span className='text-[10px] text-[var(--to-text-dim)] px-1 font-mono'>
        {format(message.timestamp, 'HH:mm')}
      </span>
    </div>
  );
}

// ── Typing Indicator ──────────────────────────────────────────────────────────

function TypingIndicator() {
  return (
    <div className='flex items-start gap-2 animate-fade-in'>
      <div
        className='flex h-5 w-5 items-center justify-center rounded-md shrink-0 mt-0.5'
        style={{
          background: 'linear-gradient(135deg,#6366f1 0%,#8b5cf6 100%)',
        }}
      >
        <Sparkles className='h-2.5 w-2.5 text-white' />
      </div>
      <div className='rounded-2xl rounded-bl-sm bg-[var(--to-surface-raised)] border border-[var(--to-border)] px-4 py-2.5'>
        <div className='flex items-center gap-2'>
          <div className='flex items-center gap-1'>
            {[0, 1, 2].map((i) => (
              <span
                key={i}
                className='inline-block w-1.5 h-1.5 rounded-full bg-[#6366f1]'
                style={{ animation: `bounce 1.2s infinite ${i * 0.2}s` }}
              />
            ))}
          </div>
          <span className='text-[10px] text-[var(--to-text-dim)] font-mono'>
            Analyzing your trades…
          </span>
        </div>
      </div>
    </div>
  );
}

// ── Quick Action Icons ────────────────────────────────────────────────────────

const ACTION_ICONS: Record<string, React.ReactNode> = {
  '💰 PnL Summary': <TrendingUp className='h-3 w-3' />,
  "📅 Today's Summary": <Calendar className='h-3 w-3' />,
  '❌ Why Rejected?': <AlertCircle className='h-3 w-3' />,
  '🏆 Best Setups': <Award className='h-3 w-3' />,
  '📊 By Symbol': <BarChart2 className='h-3 w-3' />,
  '🕐 By Session': <Zap className='h-3 w-3' />,
  '📆 By Day': <Calendar className='h-3 w-3' />,
  '📐 Sharpe Ratio': <TrendingUp className='h-3 w-3' />,
};

// ── Main Component ────────────────────────────────────────────────────────────

interface AICopilotProps {
  open: boolean;
  onClose: () => void;
}

export function AICopilot({ open, onClose }: AICopilotProps) {
  const [messages, setMessages] = useState<ExtendedMessage[]>([
    {
      role: 'assistant',
      content:
        '👋 Hi! I\'m your trading AI Copilot. Ask me anything about your trade history.\n\nTry: "Show my best setups" or "Why was the last trade rejected?"',
      timestamp: new Date(),
      followUps: [
        'Show my total PnL',
        'Win rate by symbol',
        'Show my best setups',
      ],
    },
  ]);
  const [input, setInput] = useState('');
  const [isThinking, setIsThinking] = useState(false);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  const { data: signals = [] } = useQuery({
    queryKey: ['copilot-signals'],
    queryFn: () => fetchSignals({ limit: 500 }),
    staleTime: 5 * 60 * 1000,
  });

  useEffect(() => {
    if (open) setTimeout(() => inputRef.current?.focus(), 100);
  }, [open]);
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, isThinking]);

  const sendMessage = useCallback(
    async (query: string) => {
      if (!query.trim()) return;
      const userMsg: ExtendedMessage = {
        role: 'user',
        content: query,
        timestamp: new Date(),
      };
      setMessages((prev) => [...prev, userMsg]);
      setInput('');
      setIsThinking(true);
      await new Promise((r) => setTimeout(r, 600));
      const response = queryCopilot(query, signals as TradingSignal[]);
      const assistantMsg: ExtendedMessage = {
        role: 'assistant',
        content: response.text,
        data: response.data,
        timestamp: new Date(),
        followUps: getFollowUps(query),
      };
      setIsThinking(false);
      setMessages((prev) => [...prev, assistantMsg]);
    },
    [signals]
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
        followUps: [
          'Show my total PnL',
          'Win rate by symbol',
          'Show my best setups',
        ],
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
        className='fixed right-0 top-0 bottom-0 z-50 flex min-h-0 flex-col overflow-hidden'
        style={{
          width: 'min(420px,100vw)',
          maxHeight: '100dvh',
          backgroundColor: 'var(--to-bg)',
          borderLeft: '1px solid var(--to-border)',
          boxShadow: '-20px 0 60px rgba(0,0,0,0.4)',
        }}
      >
        {/* Header */}
        <div
          className='flex items-center justify-between px-4 py-3.5 border-b border-[var(--to-border)] shrink-0'
          style={{
            background:
              'linear-gradient(135deg,#0f1320 0%,#0d1117 60%,#12101a 100%)',
          }}
        >
          <div className='flex items-center gap-3'>
            <div
              className='relative flex h-9 w-9 items-center justify-center rounded-xl shrink-0'
              style={{
                background: 'linear-gradient(135deg,#6366f1 0%,#8b5cf6 100%)',
                boxShadow: '0 0 20px rgba(99,102,241,0.45)',
              }}
            >
              <Sparkles
                className='h-4.5 w-4.5 text-white'
                style={{ width: 18, height: 18 }}
              />
              {/* Status dot */}
              <span
                className='absolute -top-0.5 -right-0.5 h-2.5 w-2.5 rounded-full bg-[#0ecb81] border-2 border-[#0d1117]'
                style={{ boxShadow: '0 0 6px #0ecb81' }}
              />
            </div>
            <div>
              <div className='text-[13px] font-semibold text-[var(--to-text-primary)]'>
                AI Copilot
              </div>
              <div className='flex items-center gap-1.5 mt-0.5'>
                <span className='text-[9px] font-mono text-[#0ecb81]'>
                  ● READY
                </span>
                <span className='text-[9px] font-mono text-[var(--to-text-dim)]'>
                  ·
                </span>
                <span className='text-[9px] font-mono text-[var(--to-text-dim)]'>
                  {signals.length} signals
                </span>
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
        <div className='px-3 py-2.5 border-b border-[var(--to-border)] shrink-0'>
          <div className='grid grid-cols-4 gap-1'>
            {QUICK_ACTIONS.map((action) => (
              <button
                key={action.query}
                onClick={() => sendMessage(action.query)}
                className='flex flex-col items-center gap-1 rounded-lg border border-[var(--to-border)] bg-[var(--to-surface-raised)] px-1 py-2 text-[9px] text-[var(--to-text-dim)] hover:border-[#6366f1]/40 hover:text-[var(--to-text-primary)] hover:bg-[#6366f1]/8 transition-all text-center leading-tight font-mono'
              >
                <span className='text-[13px] leading-none'>
                  {action.label.split(' ')[0]}
                </span>
                <span className='line-clamp-2'>
                  {action.label.split(' ').slice(1).join(' ')}
                </span>
              </button>
            ))}
          </div>
        </div>

        {/* Messages */}
        <div className='flex-1 min-h-0 overflow-y-auto overflow-x-hidden px-4 py-4 space-y-4 scrollbar-thin'>
          {messages.map((msg, i) => (
            <MessageBubble key={i} message={msg} onFollowUp={sendMessage} />
          ))}
          {isThinking && <TypingIndicator />}
          <div ref={messagesEndRef} />
        </div>

        {/* Input */}
        <div
          className='px-4 py-3.5 border-t border-[var(--to-border)] shrink-0'
          style={{
            background:
              'linear-gradient(0deg,var(--to-bg) 0%,transparent 100%)',
          }}
        >
          <form onSubmit={handleSubmit} className='flex items-center gap-2'>
            <input
              ref={inputRef}
              value={input}
              onChange={(e) => setInput(e.target.value)}
              placeholder='Ask about your trades…'
              className='flex-1 min-w-0 rounded-xl border border-[var(--to-border)] bg-[var(--to-surface-raised)] px-3.5 py-2.5 text-[12px] text-[var(--to-text-primary)] placeholder:text-[var(--to-text-dim)] outline-none focus:border-[#6366f1]/50 transition-colors'
              style={{ fontFamily: 'var(--font-sans)' }}
              disabled={isThinking}
            />
            <button
              type='submit'
              disabled={!input.trim() || isThinking}
              className='flex h-9 w-9 shrink-0 items-center justify-center rounded-xl text-white transition-all disabled:opacity-40'
              style={{
                background: 'linear-gradient(135deg,#6366f1 0%,#8b5cf6 100%)',
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
