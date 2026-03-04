'use client';

import { useMemo } from 'react';
import { TradingSignal, getPnl, getSymbol } from '@/types/trading';
import { getDay } from 'date-fns';
import { getAllTradeNotes, MOOD_OPTIONS } from './TradeNoteEditor';
import { TrendingUp, TrendingDown, AlertCircle, Brain } from 'lucide-react';

const DAY_NAMES = ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat'];
const SESSION_NAMES: Record<number, string> = {
  0: 'Asia',
  1: 'London',
  2: 'New York',
  3: 'Off',
};

interface Insight {
  icon: React.ReactNode;
  text: string;
  type: 'positive' | 'negative' | 'neutral';
}

interface PatternAnalysisProps {
  signals: TradingSignal[];
}

export function PatternAnalysis({ signals }: PatternAnalysisProps) {
  const notes = getAllTradeNotes();

  const insights = useMemo<Insight[]>(() => {
    const closed = signals.filter((s) => {
      const st = (s.status || '').toLowerCase();
      return (st === 'closed' || st === 'executed') && getPnl(s) != null;
    });

    if (closed.length < 3) return [];
    const result: Insight[] = [];

    // ── Worst day of week ────────────────────────────────────────────────
    const dayPnl = new Map<number, { pnl: number; count: number }>();
    for (const s of closed) {
      const day = getDay(new Date(s.created_at));
      const pnl = getPnl(s) ?? 0;
      const entry = dayPnl.get(day) || { pnl: 0, count: 0 };
      entry.pnl += pnl;
      entry.count++;
      dayPnl.set(day, entry);
    }
    const dayArr = Array.from(dayPnl.entries()).sort(
      (a, b) => a[1].pnl - b[1].pnl,
    );
    if (dayArr.length > 0 && dayArr[0][1].pnl < 0) {
      const [day, data] = dayArr[0];
      result.push({
        icon: <TrendingDown className='h-3.5 w-3.5' />,
        text: `You lose most on **${DAY_NAMES[day]}s** (avg ${(data.pnl / data.count).toFixed(2)} per trade, ${data.count} trades). Consider reducing position size or skipping ${DAY_NAMES[day]}s.`,
        type: 'negative',
      });
    }
    if (dayArr.length > 0 && dayArr[dayArr.length - 1][1].pnl > 0) {
      const [day, data] = dayArr[dayArr.length - 1];
      result.push({
        icon: <TrendingUp className='h-3.5 w-3.5' />,
        text: `Your best day is **${DAY_NAMES[day]}** (avg +${(data.pnl / data.count).toFixed(2)} per trade). Focus more effort here.`,
        type: 'positive',
      });
    }

    // ── Best session ─────────────────────────────────────────────────────
    const sessionPnl = new Map<
      number,
      { pnl: number; count: number; wins: number }
    >();
    for (const s of closed) {
      const sess = s.session ?? null;
      if (sess == null) continue;
      const pnl = getPnl(s) ?? 0;
      const entry = sessionPnl.get(sess) || { pnl: 0, count: 0, wins: 0 };
      entry.pnl += pnl;
      entry.count++;
      if (pnl > 0) entry.wins++;
      sessionPnl.set(sess, entry);
    }
    const bestSession = Array.from(sessionPnl.entries()).sort(
      (a, b) => b[1].pnl - a[1].pnl,
    )[0];
    const worstSession = Array.from(sessionPnl.entries()).sort(
      (a, b) => a[1].pnl - b[1].pnl,
    )[0];
    if (bestSession && bestSession[1].pnl > 0) {
      const [sess, data] = bestSession;
      result.push({
        icon: <TrendingUp className='h-3.5 w-3.5' />,
        text: `**${SESSION_NAMES[sess] || `Session ${sess}`}** is your most profitable session (${((data.wins / data.count) * 100).toFixed(0)}% WR, ${data.count} trades).`,
        type: 'positive',
      });
    }
    if (
      worstSession &&
      worstSession[1].pnl < 0 &&
      worstSession[0] !== bestSession?.[0]
    ) {
      const [sess, data] = worstSession;
      result.push({
        icon: <TrendingDown className='h-3.5 w-3.5' />,
        text: `**${SESSION_NAMES[sess] || `Session ${sess}`}** is your worst session. You've lost $${Math.abs(data.pnl).toFixed(2)} across ${data.count} trades here.`,
        type: 'negative',
      });
    }

    // ── Tagged FOMO/Revenge trades ────────────────────────────────────────
    const badTags = ['fomo', 'revenge', 'impulse', 'oversize'];
    const taggedBad = Object.values(notes).filter((n) =>
      n.tags.some((t) => badTags.includes(t)),
    );
    if (taggedBad.length > 0) {
      const matchedSignals = closed.filter((s) =>
        taggedBad.some((n) => n.signalId === s.id),
      );
      if (matchedSignals.length > 0) {
        const badPnl = matchedSignals.reduce(
          (acc, s) => acc + (getPnl(s) ?? 0),
          0,
        );
        result.push({
          icon: <AlertCircle className='h-3.5 w-3.5' />,
          text: `Emotional trades (FOMO/Revenge/Impulse) cost you **$${Math.abs(badPnl).toFixed(2)}** across ${matchedSignals.length} trade${matchedSignals.length > 1 ? 's' : ''}. These tags destroy your edge.`,
          type: 'negative',
        });
      }
    }

    // ── Best symbol ───────────────────────────────────────────────────────
    const symPnl = new Map<
      string,
      { pnl: number; count: number; wins: number }
    >();
    for (const s of closed) {
      const sym = getSymbol(s);
      const pnl = getPnl(s) ?? 0;
      const entry = symPnl.get(sym) || { pnl: 0, count: 0, wins: 0 };
      entry.pnl += pnl;
      entry.count++;
      if (pnl > 0) entry.wins++;
      symPnl.set(sym, entry);
    }
    const bestSym = Array.from(symPnl.entries())
      .filter(([, d]) => d.count >= 2)
      .sort((a, b) => b[1].pnl - a[1].pnl)[0];
    if (bestSym && bestSym[1].pnl > 0) {
      const [sym, data] = bestSym;
      result.push({
        icon: <TrendingUp className='h-3.5 w-3.5' />,
        text: `**${sym}** is your best symbol — $${data.pnl.toFixed(2)} profit, ${((data.wins / data.count) * 100).toFixed(0)}% win rate across ${data.count} trades. Consider allocating more to it.`,
        type: 'positive',
      });
    }

    // ── Mood correlation ──────────────────────────────────────────────────
    if (Object.keys(notes).length >= 3) {
      const moodPnl = new Map<string, { pnl: number; count: number }>();
      for (const [signalId, note] of Object.entries(notes)) {
        if (!note.mood) continue;
        const signal = closed.find((s) => s.id === signalId);
        if (!signal) continue;
        const pnl = getPnl(signal) ?? 0;
        const entry = moodPnl.get(note.mood) || { pnl: 0, count: 0 };
        entry.pnl += pnl;
        entry.count++;
        moodPnl.set(note.mood, entry);
      }
      const moodArr = Array.from(moodPnl.entries()).sort(
        (a, b) => b[1].pnl - a[1].pnl,
      );
      if (moodArr.length > 0) {
        const [bestMood, bestData] = moodArr[0];
        const moodMeta = MOOD_OPTIONS.find((m) => m.id === bestMood);
        if (moodMeta && bestData.pnl > 0) {
          result.push({
            icon: <Brain className='h-3.5 w-3.5' />,
            text: `You trade best when **${moodMeta.label}** (avg +$${(bestData.pnl / bestData.count).toFixed(2)}/trade). Track your mood daily.`,
            type: 'positive',
          });
        }
        if (moodArr.length > 1) {
          const [worstMood, worstData] = moodArr[moodArr.length - 1];
          const worstMoodMeta = MOOD_OPTIONS.find((m) => m.id === worstMood);
          if (worstMoodMeta && worstData.pnl < 0) {
            result.push({
              icon: <Brain className='h-3.5 w-3.5' />,
              text: `You lose most when **${worstMoodMeta.label}** (avg $${(worstData.pnl / worstData.count).toFixed(2)}/trade). Consider stepping away when feeling this way.`,
              type: 'negative',
            });
          }
        }
      }
    }

    return result.slice(0, 6); // cap at 6 insights
  }, [signals, notes]);

  if (insights.length === 0) {
    return null;
  }

  return (
    <div className='rounded-xl border border-[var(--to-border)] bg-[var(--to-surface)] p-5'>
      <div className='flex items-center gap-2 mb-4'>
        <Brain className='h-4 w-4 text-[#6366f1]' />
        <span className='text-[13px] font-semibold text-[var(--to-text-primary)]'>
          Pattern Insights
        </span>
        <span className='ml-auto text-[10px] text-[var(--to-text-dim)] font-mono'>
          {
            signals.filter((s) => {
              const st = (s.status || '').toLowerCase();
              return st === 'closed' || st === 'executed';
            }).length
          }{' '}
          trades analyzed
        </span>
      </div>
      <div className='space-y-2.5'>
        {insights.map((insight, i) => {
          const colorClass =
            insight.type === 'positive'
              ? '#0ecb81'
              : insight.type === 'negative'
                ? '#f6465d'
                : '#848e9c';
          const bgClass =
            insight.type === 'positive'
              ? '#0ecb8110'
              : insight.type === 'negative'
                ? '#f6465d10'
                : '#84848a10';
          const parts = insight.text.split(/(\*\*[^*]+\*\*)/g);
          return (
            <div
              key={i}
              className='flex items-start gap-2.5 rounded-lg px-3 py-2.5'
              style={{ backgroundColor: bgClass }}
            >
              <span style={{ color: colorClass }} className='mt-0.5 shrink-0'>
                {insight.icon}
              </span>
              <p className='text-[12px] text-[var(--to-text-secondary)] leading-relaxed'>
                {parts.map((part, j) =>
                  part.startsWith('**') && part.endsWith('**') ? (
                    <strong key={j} style={{ color: 'var(--to-text-primary)' }}>
                      {part.slice(2, -2)}
                    </strong>
                  ) : (
                    <span key={j}>{part}</span>
                  ),
                )}
              </p>
            </div>
          );
        })}
      </div>
    </div>
  );
}
