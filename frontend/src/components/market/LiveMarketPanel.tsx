'use client';

import { useState, useEffect, useCallback, useRef } from 'react';
import {
  TrendingUp,
  TrendingDown,
  Globe,
  Calendar,
  Rss,
  ChevronRight,
  RefreshCw,
  X,
  Activity,
  Clock,
  Wifi,
  WifiOff,
  AlertTriangle,
} from 'lucide-react';
import { cn } from '@/lib/utils';
import { format, differenceInMinutes } from 'date-fns';
import { API_BASE_URL } from '@/lib/api';

// ── Session Detection ─────────────────────────────────────────────────────────

interface MarketSession {
  name: string;
  color: string;
  bg: string;
}

function getActiveSessions(): MarketSession[] {
  const now = new Date();
  const t = now.getUTCHours() * 60 + now.getUTCMinutes();
  const out: MarketSession[] = [];
  if (t >= 0 && t < 540)
    out.push({ name: 'Asia', color: '#8b5cf6', bg: 'rgba(139,92,246,0.12)' });
  if (t >= 480 && t < 1020)
    out.push({ name: 'London', color: '#3b82f6', bg: 'rgba(59,130,246,0.12)' });
  if (t >= 780 && t < 1320)
    out.push({
      name: 'New York',
      color: '#0ecb81',
      bg: 'rgba(14,203,129,0.12)',
    });
  if (out.length === 0)
    out.push({ name: 'Closed', color: '#4d5666', bg: 'rgba(77,86,102,0.12)' });
  return out;
}

function SessionBar() {
  const [sessions, setSessions] = useState<MarketSession[]>(
    getActiveSessions()
  );
  const [utcTime, setUtcTime] = useState('');
  useEffect(() => {
    const tick = () => {
      setSessions(getActiveSessions());
      const n = new Date();
      setUtcTime(
        `${String(n.getUTCHours()).padStart(2, '0')}:${String(
          n.getUTCMinutes()
        ).padStart(2, '0')}:${String(n.getUTCSeconds()).padStart(2, '0')} UTC`
      );
    };
    tick();
    const id = setInterval(tick, 1000);
    return () => clearInterval(id);
  }, []);
  return (
    <div className='flex items-center justify-between px-1 py-2 mb-1'>
      <div className='flex items-center gap-1.5 flex-wrap'>
        {sessions.map((s) => (
          <span
            key={s.name}
            className='flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-semibold font-mono'
            style={{
              color: s.color,
              backgroundColor: s.bg,
              border: `1px solid ${s.color}30`,
            }}
          >
            <span
              className='inline-block w-1.5 h-1.5 rounded-full'
              style={{
                backgroundColor: s.color,
                boxShadow: `0 0 6px ${s.color}`,
              }}
            />
            {s.name}
          </span>
        ))}
      </div>
      <div className='flex items-center gap-1 text-[9px] font-mono text-[var(--to-text-dim)] shrink-0'>
        <Clock className='h-2.5 w-2.5' />
        {utcTime}
      </div>
    </div>
  );
}

// ── Price Feed ────────────────────────────────────────────────────────────────

const WATCH_SYMBOLS = [
  { symbol: 'XAUUSD', display: 'XAU/USD', yahooId: 'GC=F', category: 'Metal' },
  {
    symbol: 'EURUSD',
    display: 'EUR/USD',
    yahooId: 'EURUSD=X',
    category: 'Forex',
  },
  {
    symbol: 'GBPUSD',
    display: 'GBP/USD',
    yahooId: 'GBPUSD=X',
    category: 'Forex',
  },
  { symbol: 'USDJPY', display: 'USD/JPY', yahooId: 'JPY=X', category: 'Forex' },
  {
    symbol: 'GBPJPY',
    display: 'GBP/JPY',
    yahooId: 'GBPJPY=X',
    category: 'Forex',
  },
  { symbol: 'NAS100', display: 'NAS 100', yahooId: 'NQ=F', category: 'Index' },
  {
    symbol: 'BTCUSD',
    display: 'BTC/USD',
    yahooId: 'BTC-USD',
    category: 'Crypto',
  },
];

interface PriceData {
  symbol: string;
  display: string;
  category: string;
  price: number | null;
  change: number | null;
  changePct: number | null;
  lastUpdated: Date;
  flash: 'up' | 'down' | null;
}

function usePriceFeed() {
  const [prices, setPrices] = useState<PriceData[]>(
    WATCH_SYMBOLS.map((s) => ({
      ...s,
      price: null,
      change: null,
      changePct: null,
      lastUpdated: new Date(),
      flash: null,
    }))
  );
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(false);
  const [lastRefresh, setLastRefresh] = useState<Date | null>(null);
  const prev = useRef<Record<string, number | null>>({});

  const fetchPrices = useCallback(async () => {
    try {
      setError(false);
      const syms = WATCH_SYMBOLS.map((s) => s.yahooId).join(',');
      const res = await fetch(
        `${API_BASE_URL}/api/market/prices?symbols=${encodeURIComponent(
          syms
        )}&interval=1d&range=1d`,
        { signal: AbortSignal.timeout(10000) }
      );
      if (!res.ok) throw new Error('err');
      const data = (await res.json()) as Array<{
        symbol: string;
        price: number | null;
        change: number | null;
        changePct: number | null;
      }>;
      const byId = Object.fromEntries(data.map((d) => [d.symbol, d]));
      setPrices(
        WATCH_SYMBOLS.map((sym) => {
          const row = byId[sym.yahooId];
          const np = row?.price ?? null;
          const op = prev.current[sym.symbol] ?? null;
          const flash: 'up' | 'down' | null =
            np != null && op != null && np !== op
              ? np > op
                ? 'up'
                : 'down'
              : null;
          prev.current[sym.symbol] = np;
          return {
            ...sym,
            price: np,
            change: row?.change ?? null,
            changePct: row?.changePct ?? null,
            lastUpdated: new Date(),
            flash,
          };
        })
      );
      setTimeout(
        () => setPrices((p) => p.map((x) => ({ ...x, flash: null }))),
        800
      );
      setLastRefresh(new Date());
    } catch {
      setError(true);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchPrices();
    const id = setInterval(fetchPrices, 30_000);
    return () => clearInterval(id);
  }, [fetchPrices]);
  return { prices, loading, error, lastRefresh, refetch: fetchPrices };
}

function fmtPrice(p: PriceData) {
  if (p.price == null) return '—';
  if (p.symbol.includes('JPY')) return p.price.toFixed(3);
  if (
    p.symbol === 'XAUUSD' ||
    p.symbol === 'BTCUSD' ||
    p.symbol.includes('NAS')
  )
    return p.price.toFixed(2);
  return p.price.toFixed(5);
}
function fmtChange(p: PriceData) {
  if (p.change == null) return '';
  const pfx = p.change >= 0 ? '+' : '';
  if (p.symbol.includes('JPY')) return `${pfx}${p.change.toFixed(3)}`;
  if (
    p.symbol === 'XAUUSD' ||
    p.symbol === 'BTCUSD' ||
    p.symbol.includes('NAS')
  )
    return `${pfx}${p.change.toFixed(2)}`;
  return `${pfx}${p.change.toFixed(5)}`;
}

function PriceRow({ p }: { p: PriceData }) {
  const isUp = (p.changePct ?? 0) >= 0;
  const rowBg = p.flash
    ? p.flash === 'up'
      ? 'rgba(14,203,129,0.08)'
      : 'rgba(246,70,93,0.08)'
    : p.changePct != null
    ? isUp
      ? 'rgba(14,203,129,0.03)'
      : 'rgba(246,70,93,0.03)'
    : 'var(--to-surface-raised)';
  const rowBorder = p.flash
    ? p.flash === 'up'
      ? 'rgba(14,203,129,0.5)'
      : 'rgba(246,70,93,0.5)'
    : 'var(--to-border)';
  return (
    <div
      className='flex items-center justify-between px-3 py-2.5 rounded-xl border transition-all duration-300'
      style={{ borderColor: rowBorder, backgroundColor: rowBg }}
    >
      <div className='flex flex-col gap-0.5 min-w-0'>
        <div className='flex items-center gap-1.5'>
          <span className='text-[13px] font-bold font-mono text-[var(--to-text-primary)]'>
            {p.display}
          </span>
          <span
            className='text-[8px] font-mono font-semibold px-1 py-0.5 rounded'
            style={{
              color: 'var(--to-text-dim)',
              backgroundColor: 'var(--to-surface)',
              border: '1px solid var(--to-border)',
            }}
          >
            {p.category}
          </span>
        </div>
        {p.change != null ? (
          <span
            className='text-[10px] font-mono'
            style={{ color: isUp ? '#0ecb81' : '#f6465d' }}
          >
            {fmtChange(p)}
          </span>
        ) : (
          <span className='h-3 w-16 rounded bg-[var(--to-surface)] animate-pulse' />
        )}
      </div>
      <div className='flex flex-col items-end gap-1 shrink-0'>
        <span
          className='text-[15px] font-bold font-mono tabular-nums transition-colors duration-300'
          style={{
            color: p.flash
              ? p.flash === 'up'
                ? '#0ecb81'
                : '#f6465d'
              : 'var(--to-text-primary)',
          }}
        >
          {fmtPrice(p)}
        </span>
        {p.changePct != null ? (
          <span
            className='flex items-center gap-0.5 px-1.5 py-0.5 rounded-full text-[10px] font-mono font-bold'
            style={{
              color: isUp ? '#0ecb81' : '#f6465d',
              backgroundColor: isUp
                ? 'rgba(14,203,129,0.12)'
                : 'rgba(246,70,93,0.12)',
            }}
          >
            {isUp ? (
              <TrendingUp className='h-2.5 w-2.5' />
            ) : (
              <TrendingDown className='h-2.5 w-2.5' />
            )}
            {isUp ? '+' : ''}
            {p.changePct.toFixed(2)}%
          </span>
        ) : (
          <span className='h-5 w-14 rounded-full bg-[var(--to-surface)] animate-pulse' />
        )}
      </div>
    </div>
  );
}

function PriceTicker() {
  const { prices, loading, error, lastRefresh, refetch } = usePriceFeed();
  return (
    <div className='space-y-2'>
      <SessionBar />
      <div className='flex items-center justify-between mb-1'>
        <div className='flex items-center gap-1.5'>
          {error ? (
            <>
              <WifiOff className='h-3 w-3 text-[#f6465d]' />
              <span className='text-[10px] text-[#f6465d] font-mono'>
                Feed error
              </span>
            </>
          ) : (
            <>
              <Wifi className='h-3 w-3 text-[#0ecb81]' />
              <span className='text-[10px] text-[var(--to-text-dim)] font-mono'>
                {lastRefresh
                  ? `Updated ${format(lastRefresh, 'HH:mm:ss')}`
                  : 'Loading…'}
              </span>
            </>
          )}
        </div>
        <button
          onClick={refetch}
          className='text-[var(--to-text-dim)] hover:text-[var(--to-text-secondary)] transition-colors'
          title='Refresh'
        >
          <RefreshCw className={cn('h-3 w-3', loading && 'animate-spin')} />
        </button>
      </div>
      <div className='space-y-1.5'>
        {prices.map((p) => (
          <PriceRow key={p.symbol} p={p} />
        ))}
      </div>
      <p className='text-[9px] text-[var(--to-text-dim)] text-center font-mono pt-1'>
        Prices delayed ~15 min · Refreshes every 30s
      </p>
    </div>
  );
}

// ── Economic Calendar ─────────────────────────────────────────────────────────

type ImpactLevel = 'high' | 'medium' | 'low';
const SAMPLE_EVENTS = [
  {
    time: '08:30',
    currency: 'USD',
    event: 'Non-Farm Payrolls',
    impact: 'high' as ImpactLevel,
    forecast: '185K',
    previous: '175K',
  },
  {
    time: '10:00',
    currency: 'USD',
    event: 'ISM Manufacturing PMI',
    impact: 'medium' as ImpactLevel,
    forecast: '49.5',
    previous: '48.7',
  },
  {
    time: '13:30',
    currency: 'GBP',
    event: 'BoE Interest Rate Decision',
    impact: 'high' as ImpactLevel,
    forecast: '5.25%',
    previous: '5.25%',
  },
  {
    time: '15:00',
    currency: 'EUR',
    event: 'ECB Press Conference',
    impact: 'high' as ImpactLevel,
    forecast: '—',
    previous: '—',
  },
  {
    time: '18:00',
    currency: 'JPY',
    event: 'Trade Balance',
    impact: 'low' as ImpactLevel,
    forecast: '¥0.3T',
    previous: '¥0.1T',
  },
];
const IMPACT_CFG: Record<
  ImpactLevel,
  { color: string; bg: string; label: string }
> = {
  high: { color: '#f6465d', bg: 'rgba(246,70,93,0.12)', label: 'HIGH' },
  medium: { color: '#f0b90b', bg: 'rgba(240,185,11,0.12)', label: 'MED' },
  low: { color: '#4d5666', bg: 'rgba(77,86,102,0.12)', label: 'LOW' },
};

function EconomicCalendar() {
  const [filter, setFilter] = useState<'all' | ImpactLevel>('all');
  const now = new Date();
  const nowStr = format(now, 'HH:mm');
  const filtered = SAMPLE_EVENTS.filter(
    (ev) => filter === 'all' || ev.impact === filter
  );
  const nextEvent = SAMPLE_EVENTS.find((ev) => ev.time > nowStr);

  return (
    <div className='space-y-2'>
      <div className='flex items-center justify-between'>
        <span className='text-[10px] text-[var(--to-text-dim)] font-mono'>
          {format(now, 'EEEE, MMM dd yyyy')}
        </span>
        {nextEvent && (
          <span className='text-[9px] font-mono text-[#f0b90b] flex items-center gap-1'>
            <Clock className='h-2.5 w-2.5' />
            Next: {nextEvent.time}
          </span>
        )}
      </div>

      {/* Impact filter */}
      <div className='flex gap-1'>
        {(['all', 'high', 'medium', 'low'] as const).map((f) => {
          const active = filter === f;
          const cfg = f !== 'all' ? IMPACT_CFG[f] : null;
          return (
            <button
              key={f}
              onClick={() => setFilter(f)}
              className='flex-1 py-1 rounded-lg text-[9px] font-mono font-bold uppercase transition-all border'
              style={
                active && cfg
                  ? {
                      backgroundColor: cfg.bg,
                      color: cfg.color,
                      borderColor: `${cfg.color}40`,
                    }
                  : active
                  ? {
                      backgroundColor: 'var(--to-surface-raised)',
                      color: 'var(--to-text-primary)',
                      borderColor: 'var(--to-border)',
                    }
                  : {
                      backgroundColor: 'transparent',
                      color: 'var(--to-text-dim)',
                      borderColor: 'var(--to-border)',
                    }
              }
            >
              {f === 'all'
                ? 'All'
                : f === 'high'
                ? '🔴 High'
                : f === 'medium'
                ? '🟡 Med'
                : '⚪ Low'}
            </button>
          );
        })}
      </div>

      {/* Events */}
      <div className='space-y-1.5'>
        {filtered.map((ev, i) => {
          const isPast = ev.time < nowStr;
          const isNext = ev === nextEvent;
          const cfg = IMPACT_CFG[ev.impact];
          return (
            <div
              key={i}
              className='rounded-xl border transition-all overflow-hidden'
              style={{
                opacity: isPast ? 0.45 : 1,
                borderColor: isNext ? `${cfg.color}50` : 'var(--to-border)',
                backgroundColor: isNext ? cfg.bg : 'var(--to-surface-raised)',
                boxShadow: isNext ? `0 0 12px ${cfg.color}20` : 'none',
              }}
            >
              <div className='flex items-center gap-2 px-3 py-2'>
                <span className='text-[10px] font-mono text-[var(--to-text-dim)] w-10 shrink-0'>
                  {ev.time}
                </span>
                <span
                  className='text-[8px] font-mono font-bold px-1.5 py-0.5 rounded shrink-0'
                  style={{ color: cfg.color, backgroundColor: cfg.bg }}
                >
                  {cfg.label}
                </span>
                <span className='text-[10px] font-mono font-bold text-[var(--to-text-secondary)] w-8 shrink-0'>
                  {ev.currency}
                </span>
                <span className='text-[11px] text-[var(--to-text-primary)] truncate flex-1 font-medium'>
                  {ev.event}
                </span>
              </div>
              {!isPast && (ev.forecast !== '—' || ev.previous !== '—') && (
                <div
                  className='flex items-center gap-4 px-3 pb-2 pt-1'
                  style={{ borderTop: '1px solid rgba(33,38,45,0.6)' }}
                >
                  <span className='text-[9px] font-mono text-[var(--to-text-dim)]'>
                    Forecast:{' '}
                    <span className='text-[var(--to-text-secondary)]'>
                      {ev.forecast}
                    </span>
                  </span>
                  <span className='text-[9px] font-mono text-[var(--to-text-dim)]'>
                    Prev:{' '}
                    <span className='text-[var(--to-text-secondary)]'>
                      {ev.previous}
                    </span>
                  </span>
                </div>
              )}
            </div>
          );
        })}
      </div>
      <div className='text-[9px] text-[var(--to-text-dim)] text-center mt-2 font-mono'>
        Sample events · Connect to a calendar API for live data
      </div>
    </div>
  );
}

// ── News Feed ─────────────────────────────────────────────────────────────────

interface NewsItem {
  title: string;
  source: string;
  url: string;
  pubDate: string;
}

function useNewsFeed() {
  const [items, setItems] = useState<NewsItem[]>([]);
  const [loading, setLoading] = useState(true);
  useEffect(() => {
    const go = async () => {
      try {
        const res = await fetch(
          'https://api.rss2json.com/v1/api.json?rss_url=https://feeds.content.dowjones.io/public/rss/mw_realtimeheadlines',
          { signal: AbortSignal.timeout(5000) }
        );
        const json = await res.json();
        if (json.items)
          setItems(
            json.items.slice(0, 8).map((it: Record<string, unknown>) => ({
              title: (it.title as string) || '',
              source: (it.author as string) || 'MarketWatch',
              url: (it.link as string) || '#',
              pubDate: (it.pubDate as string) || '',
            }))
          );
      } catch {
        /* silent */
      } finally {
        setLoading(false);
      }
    };
    go();
    const id = setInterval(go, 5 * 60_000);
    return () => clearInterval(id);
  }, []);
  return { items, loading };
}

function NewsCard({ item }: { item: NewsItem }) {
  const timeAgo = item.pubDate
    ? (() => {
        try {
          const m = differenceInMinutes(new Date(), new Date(item.pubDate));
          return m < 60 ? `${m}m ago` : `${Math.floor(m / 60)}h ago`;
        } catch {
          return '';
        }
      })()
    : '';
  return (
    <a
      href={item.url}
      target='_blank'
      rel='noopener noreferrer'
      className='block rounded-xl border border-[var(--to-border)] bg-[var(--to-surface-raised)] hover:bg-[var(--to-surface)] transition-all group'
    >
      <div className='px-3 py-2.5'>
        <p className='text-[11px] text-[var(--to-text-primary)] leading-snug line-clamp-2 group-hover:text-white transition-colors'>
          {item.title}
        </p>
        <div className='flex items-center gap-2 mt-2'>
          <span
            className='text-[8px] font-mono font-bold px-1.5 py-0.5 rounded'
            style={{
              color: '#3b82f6',
              backgroundColor: 'rgba(59,130,246,0.12)',
              border: '1px solid rgba(59,130,246,0.2)',
            }}
          >
            {item.source.slice(0, 14).toUpperCase()}
          </span>
          {timeAgo && (
            <span className='text-[9px] text-[var(--to-text-dim)] font-mono flex items-center gap-0.5'>
              <Clock className='h-2 w-2' />
              {timeAgo}
            </span>
          )}
          <ChevronRight className='h-3 w-3 text-[var(--to-text-dim)] ml-auto group-hover:text-[var(--to-text-secondary)] transition-colors' />
        </div>
      </div>
    </a>
  );
}

function NewsFeed() {
  const { items, loading } = useNewsFeed();
  if (loading)
    return (
      <div className='space-y-2'>
        {[1, 2, 3, 4].map((i) => (
          <div
            key={i}
            className='h-16 rounded-xl bg-[var(--to-surface-raised)] animate-pulse'
            style={{ opacity: 1 - i * 0.15 }}
          />
        ))}
      </div>
    );
  if (items.length === 0)
    return (
      <div className='flex flex-col items-center justify-center py-10 gap-3'>
        <div
          className='flex h-10 w-10 items-center justify-center rounded-xl'
          style={{
            backgroundColor: 'rgba(77,86,102,0.2)',
            border: '1px solid var(--to-border)',
          }}
        >
          <AlertTriangle className='h-5 w-5 text-[var(--to-text-dim)]' />
        </div>
        <p className='text-[11px] text-[var(--to-text-dim)] text-center font-mono'>
          News feed unavailable
          <br />
          Check your internet connection
        </p>
      </div>
    );
  return (
    <div className='space-y-1.5'>
      {items.map((item, i) => (
        <NewsCard key={i} item={item} />
      ))}
    </div>
  );
}

// ── Main Panel ────────────────────────────────────────────────────────────────

type MarketTab = 'prices' | 'calendar' | 'news';

interface LiveMarketPanelProps {
  open: boolean;
  onClose: () => void;
}

export function LiveMarketPanel({ open, onClose }: LiveMarketPanelProps) {
  const [tab, setTab] = useState<MarketTab>('prices');
  if (!open) return null;

  const tabs: { key: MarketTab; label: string; icon: React.ReactNode }[] = [
    { key: 'prices', label: 'Prices', icon: <Activity className='h-3 w-3' /> },
    {
      key: 'calendar',
      label: 'Calendar',
      icon: <Calendar className='h-3 w-3' />,
    },
    { key: 'news', label: 'News', icon: <Rss className='h-3 w-3' /> },
  ];

  return (
    <>
      <div className='fixed inset-0 z-40 bg-black/10' onClick={onClose} />
      <div
        className='fixed left-[72px] top-[76px] z-50 flex flex-col rounded-2xl border border-[var(--to-border)] shadow-[0_24px_64px_rgba(0,0,0,0.55)]'
        style={{
          width: 380,
          maxHeight: 'min(80vh,780px)',
          background: 'linear-gradient(160deg,#0d1117 0%,#080b10 100%)',
        }}
      >
        {/* Header */}
        <div
          className='flex items-center justify-between px-4 py-3 border-b border-[var(--to-border)] shrink-0 rounded-t-2xl'
          style={{
            background: 'linear-gradient(135deg,#0d1117 0%,#12161c 100%)',
          }}
        >
          <div className='flex items-center gap-2.5'>
            <div
              className='flex h-7 w-7 items-center justify-center rounded-lg shrink-0'
              style={{
                background: 'linear-gradient(135deg,#0ecb81 0%,#059669 100%)',
                boxShadow: '0 0 12px rgba(14,203,129,0.35)',
              }}
            >
              <Globe className='h-3.5 w-3.5 text-white' />
            </div>
            <div>
              <span className='text-[13px] font-semibold text-[var(--to-text-primary)]'>
                Live Market
              </span>
              <div className='flex items-center gap-1 mt-0.5'>
                <span
                  className='inline-block w-1.5 h-1.5 rounded-full bg-[#0ecb81] pulse-active'
                  style={{ boxShadow: '0 0 6px #0ecb81' }}
                />
                <span className='text-[9px] font-mono text-[#0ecb81]'>
                  LIVE
                </span>
              </div>
            </div>
          </div>
          <button
            onClick={onClose}
            className='flex h-7 w-7 items-center justify-center rounded-lg text-[var(--to-text-dim)] hover:bg-[var(--to-surface-raised)] hover:text-[var(--to-text-secondary)] transition-colors'
          >
            <X className='h-4 w-4' />
          </button>
        </div>

        {/* Tab bar */}
        <div className='flex border-b border-[var(--to-border)] shrink-0 px-1.5 py-1 gap-1'>
          {tabs.map((t) => (
            <button
              key={t.key}
              onClick={() => setTab(t.key)}
              className={cn(
                'flex-1 flex items-center justify-center gap-1.5 rounded-lg py-1.5 text-[11px] font-medium transition-all border',
                tab === t.key
                  ? 'border-[#0ecb81]/40 bg-[#0ecb81]/10 text-[#0ecb81]'
                  : 'border-transparent text-[var(--to-text-dim)] hover:border-white/10 hover:bg-[var(--to-surface-raised)] hover:text-[var(--to-text-secondary)]'
              )}
            >
              {t.icon}
              {t.label}
            </button>
          ))}
        </div>

        {/* Content */}
        <div className='flex-1 overflow-y-auto p-3 scrollbar-thin min-h-0'>
          {tab === 'prices' && <PriceTicker />}
          {tab === 'calendar' && <EconomicCalendar />}
          {tab === 'news' && <NewsFeed />}
        </div>
      </div>
    </>
  );
}

// ── Trigger Button ────────────────────────────────────────────────────────────

export function LiveMarketTrigger({
  onClick,
  active,
}: {
  onClick: () => void;
  active: boolean;
}) {
  return (
    <button
      onClick={onClick}
      id='live-market-trigger'
      className={cn(
        'flex items-center gap-1.5 rounded border px-2 py-0.5 text-[10px] transition-all',
        active
          ? 'border-[#0ecb81]/50 bg-[#0ecb81]/10 text-[#0ecb81]'
          : 'border-[var(--to-border)] bg-[var(--to-surface)] text-[var(--to-text-dim)] hover:border-[#0ecb81]/50 hover:text-[#0ecb81]'
      )}
      title='Live Market Panel'
    >
      <Globe className='h-3 w-3' />
      <span style={{ fontFamily: 'var(--font-mono)' }}>Markets</span>
    </button>
  );
}
