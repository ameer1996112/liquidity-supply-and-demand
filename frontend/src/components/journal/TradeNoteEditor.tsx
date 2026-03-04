'use client';

import { useState, useEffect, useCallback } from 'react';
import { TradingSignal, getSymbol, getSide, getPnl } from '@/types/trading';
import { format } from 'date-fns';
import { Save, Tag, Smile, X, CheckCircle2 } from 'lucide-react';
import { cn } from '@/lib/utils';
import { PnLText } from '@/components/ui/typography';

// ── Types ──────────────────────────────────────────────────────────────────────

export interface TradeNote {
  signalId: string;
  notes: string;
  tags: string[];
  mood: string | null;
  updatedAt: string;
}

// ── localStorage helpers ───────────────────────────────────────────────────────

const STORAGE_KEY = 'trade_notes_v1';

export function getTradeNote(signalId: string): TradeNote | null {
  if (typeof window === 'undefined') return null;
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) return null;
    const store = JSON.parse(raw) as Record<string, TradeNote>;
    return store[signalId] ?? null;
  } catch {
    return null;
  }
}

export function saveTradeNote(note: TradeNote): void {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    const store = raw ? (JSON.parse(raw) as Record<string, TradeNote>) : {};
    store[note.signalId] = note;
    localStorage.setItem(STORAGE_KEY, JSON.stringify(store));
  } catch {
    // localStorage not available
  }
}

export function getAllTradeNotes(): Record<string, TradeNote> {
  if (typeof window === 'undefined') return {};
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    return raw ? (JSON.parse(raw) as Record<string, TradeNote>) : {};
  } catch {
    return {};
  }
}

// ── Constants ──────────────────────────────────────────────────────────────────

export const TRADE_TAGS = [
  { id: 'disciplined', label: '✅ Disciplined', color: '#0ecb81' },
  { id: 'setup', label: '📐 Clean Setup', color: '#3b82f6' },
  { id: 'news', label: '📰 News-Driven', color: '#f0b90b' },
  { id: 'fomo', label: '⚡ FOMO', color: '#f6465d' },
  { id: 'revenge', label: '😠 Revenge', color: '#f6465d' },
  { id: 'oversize', label: '📦 Oversized', color: '#f0b90b' },
  { id: 'early', label: '⏰ Too Early', color: '#a78bfa' },
  { id: 'late', label: '⌛ Too Late', color: '#a78bfa' },
  { id: 'patient', label: '🎯 Patient Wait', color: '#0ecb81' },
  { id: 'plan', label: '📋 Followed Plan', color: '#0ecb81' },
  { id: 'impulse', label: '🎲 Impulsive', color: '#f6465d' },
  { id: 'boredom', label: '😴 Boredom Trade', color: '#848e9c' },
];

export const MOOD_OPTIONS = [
  { id: 'calm', label: '😊 Calm', color: '#0ecb81' },
  { id: 'focused', label: '🎯 Focused', color: '#3b82f6' },
  { id: 'confident', label: '💪 Confident', color: '#0ecb81' },
  { id: 'nervous', label: '😰 Nervous', color: '#f0b90b' },
  { id: 'frustrated', label: '😤 Frustrated', color: '#f6465d' },
  { id: 'greedy', label: '🤑 Greedy', color: '#f6465d' },
  { id: 'tired', label: '😴 Tired', color: '#848e9c' },
  { id: 'excited', label: '🔥 Excited', color: '#f0b90b' },
];

// ── Trade Note Editor ──────────────────────────────────────────────────────────

interface TradeNoteEditorProps {
  signal: TradingSignal;
  onClose?: () => void;
  compact?: boolean;
}

export function TradeNoteEditor({
  signal,
  onClose,
  compact = false,
}: TradeNoteEditorProps) {
  const [notes, setNotes] = useState('');
  const [tags, setTags] = useState<string[]>([]);
  const [mood, setMood] = useState<string | null>(null);
  const [saved, setSaved] = useState(false);

  useEffect(() => {
    const existing = getTradeNote(signal.id);
    if (existing) {
      setNotes(existing.notes);
      setTags(existing.tags);
      setMood(existing.mood);
    }
  }, [signal.id]);

  const handleSave = useCallback(() => {
    saveTradeNote({
      signalId: signal.id,
      notes,
      tags,
      mood,
      updatedAt: new Date().toISOString(),
    });
    setSaved(true);
    setTimeout(() => setSaved(false), 2000);
  }, [signal.id, notes, tags, mood]);

  const toggleTag = (tagId: string) => {
    setTags((prev) =>
      prev.includes(tagId) ? prev.filter((t) => t !== tagId) : [...prev, tagId],
    );
  };

  const pnl = getPnl(signal);
  const sym = getSymbol(signal);
  const side = getSide(signal);

  return (
    <div className={cn('flex flex-col gap-4', compact ? 'p-4' : 'p-6')}>
      {/* Trade header */}
      <div className='flex items-center justify-between'>
        <div className='flex items-center gap-3'>
          <div className='flex flex-col'>
            <div className='flex items-center gap-2'>
              <span className='font-mono font-bold text-[var(--to-text-primary)]'>
                {sym}
              </span>
              <span
                className='px-1.5 py-0.5 rounded text-[10px] font-bold'
                style={{
                  backgroundColor: side === 'buy' ? '#0ecb8120' : '#f6465d20',
                  color: side === 'buy' ? '#0ecb81' : '#f6465d',
                }}
              >
                {side.toUpperCase()}
              </span>
              {pnl != null && (
                <PnLText value={pnl} variant='currency' size='sm' />
              )}
            </div>
            <div className='text-[11px] text-[var(--to-text-dim)] mt-0.5 font-mono'>
              {format(new Date(signal.created_at), 'MMM dd, yyyy HH:mm')}
            </div>
          </div>
        </div>
        {onClose && (
          <button
            onClick={onClose}
            className='text-[var(--to-text-dim)] hover:text-[var(--to-text-primary)] transition-colors'
          >
            <X className='h-4 w-4' />
          </button>
        )}
      </div>

      {/* Mood Selector */}
      <div>
        <div className='flex items-center gap-1.5 mb-2'>
          <Smile className='h-3.5 w-3.5 text-[var(--to-text-dim)]' />
          <span className='text-[11px] font-semibold text-[var(--to-text-secondary)] uppercase tracking-wider'>
            How were you feeling?
          </span>
        </div>
        <div className='flex flex-wrap gap-1.5'>
          {MOOD_OPTIONS.map((m) => (
            <button
              key={m.id}
              onClick={() => setMood(mood === m.id ? null : m.id)}
              className='rounded-full border px-2.5 py-1 text-[11px] transition-all'
              style={{
                borderColor: mood === m.id ? m.color : 'var(--to-border)',
                backgroundColor:
                  mood === m.id ? `${m.color}15` : 'var(--to-surface-raised)',
                color: mood === m.id ? m.color : 'var(--to-text-secondary)',
              }}
            >
              {m.label}
            </button>
          ))}
        </div>
      </div>

      {/* Tag Selector */}
      <div>
        <div className='flex items-center gap-1.5 mb-2'>
          <Tag className='h-3.5 w-3.5 text-[var(--to-text-dim)]' />
          <span className='text-[11px] font-semibold text-[var(--to-text-secondary)] uppercase tracking-wider'>
            Trade Tags
          </span>
        </div>
        <div className='flex flex-wrap gap-1.5'>
          {TRADE_TAGS.map((tag) => (
            <button
              key={tag.id}
              onClick={() => toggleTag(tag.id)}
              className='rounded-full border px-2.5 py-1 text-[11px] transition-all'
              style={{
                borderColor: tags.includes(tag.id)
                  ? tag.color
                  : 'var(--to-border)',
                backgroundColor: tags.includes(tag.id)
                  ? `${tag.color}15`
                  : 'var(--to-surface-raised)',
                color: tags.includes(tag.id)
                  ? tag.color
                  : 'var(--to-text-secondary)',
              }}
            >
              {tag.label}
            </button>
          ))}
        </div>
      </div>

      {/* Notes textarea */}
      <div>
        <span className='text-[11px] font-semibold text-[var(--to-text-secondary)] uppercase tracking-wider block mb-1.5'>
          Notes
        </span>
        <textarea
          value={notes}
          onChange={(e) => setNotes(e.target.value)}
          placeholder='What did you see? What went right/wrong? Lessons learned...'
          rows={compact ? 3 : 5}
          className='w-full resize-none rounded-lg border border-[var(--to-border)] bg-[var(--to-surface-raised)] px-3 py-2.5 text-[12px] text-[var(--to-text-primary)] placeholder:text-[var(--to-text-dim)] outline-none focus:border-[#6366f1]/50 transition-colors leading-relaxed'
        />
      </div>

      {/* Save button */}
      <div className='flex items-center justify-end gap-2'>
        {saved && (
          <span className='flex items-center gap-1.5 text-[11px] text-[#0ecb81]'>
            <CheckCircle2 className='h-3.5 w-3.5' />
            Saved!
          </span>
        )}
        <button
          onClick={handleSave}
          className='flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-[12px] font-medium text-white transition-all'
          style={{
            background: 'linear-gradient(135deg, #6366f1 0%, #8b5cf6 100%)',
          }}
        >
          <Save className='h-3.5 w-3.5' />
          Save Note
        </button>
      </div>
    </div>
  );
}

// ── Compact Note Indicator for trade rows ──────────────────────────────────────

export function TradeNoteIndicator({ signalId }: { signalId: string }) {
  const [note, setNote] = useState<TradeNote | null>(null);

  useEffect(() => {
    setNote(getTradeNote(signalId));
  }, [signalId]);

  if (!note) return null;

  const hasTags = note.tags.length > 0;
  const hasMood = !!note.mood;
  const hasNotes = !!note.notes.trim();

  if (!hasTags && !hasMood && !hasNotes) return null;

  const moodEmoji = MOOD_OPTIONS.find((m) => m.id === note.mood)?.label.split(
    ' ',
  )[0];

  return (
    <div className='flex items-center gap-1'>
      {hasMood && moodEmoji && (
        <span className='text-[11px]' title={`Mood: ${note.mood}`}>
          {moodEmoji}
        </span>
      )}
      {hasNotes && (
        <span
          className='text-[10px] px-1 rounded bg-[#6366f1]/15 text-[#8b5cf6]'
          title='Has notes'
        >
          📝
        </span>
      )}
      {hasTags &&
        note.tags.slice(0, 2).map((tagId) => {
          const tag = TRADE_TAGS.find((t) => t.id === tagId);
          return tag ? (
            <span
              key={tagId}
              className='text-[9px] px-1.5 py-0.5 rounded-full border font-medium'
              style={{
                borderColor: `${tag.color}40`,
                color: tag.color,
                backgroundColor: `${tag.color}10`,
              }}
            >
              {tag.label.split(' ')[1]}
            </span>
          ) : null;
        })}
      {note.tags.length > 2 && (
        <span className='text-[9px] text-[var(--to-text-dim)]'>
          +{note.tags.length - 2}
        </span>
      )}
    </div>
  );
}
