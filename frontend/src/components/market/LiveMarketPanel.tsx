'use client';

import { useState, useEffect, useCallback } from 'react';
import {
  TrendingUp,
  TrendingDown,
  Globe,
  Calendar,
  Rss,
  ChevronRight,
  RefreshCw,
  X,
} from 'lucide-react';
import { cn } from '@/lib/utils';
import { format } from 'date-fns';
import { API_BASE_URL } from '@/lib/api';

// ── Price Ticker ──────────────────────────────────────────────────────────────

const WATCH_SYMBOLS = [
  { symbol: 'XAUUSD', display: 'XAU/USD', yahooId: 'GC=F' },
  { symbol: 'EURUSD', display: 'EUR/USD', yahooId: 'EURUSD=X' },
  { symbol: 'GBPUSD', display: 'GBP/USD', yahooId: 'GBPUSD=X' },
  { symbol: 'USDJPY', display: 'USD/JPY', yahooId: 'JPY=X' },
  { symbol: 'GBPJPY', display: 'GBP/JPY', yahooId: 'GBPJPY=X' },
  { symbol: 'NAS100', display: 'NAS 100', yahooId: 'NQ=F' },
  { symbol: 'BTCUSD', display: 'BTC/USD', yahooId: 'BTC-USD' },
];

interface PriceData {
  symbol: string;
  display: string;
  price: number | null;
  change: number | null;
  changePct: number | null;
  lastUpdated: Date;
}

function usePriceFeed() {
  const [prices, setPrices] = useState<PriceData[]>(
    WATCH_SYMBOLS.map((s) => ({
      ...s,
      price: null,
      change: null,
      changePct: null,
      lastUpdated: new Date(),
    }))
  );
  const [loading, setLoading] = useState(true);
  const [lastRefresh, setLastRefresh] = useState<Date | null>(null);

  const fetchPrices = useCallback(async () => {
    try {
      const symbols = WATCH_SYMBOLS.map((s) => s.yahooId).join(',');
      const res = await fetch(
        `${API_BASE_URL}/api/market/prices?symbols=${encodeURIComponent(
          symbols
        )}&interval=1d&range=1d`,
        { signal: AbortSignal.timeout(10000) }
      );
      if (!res.ok) throw new Error('Market data unavailable');
      const data = (await res.json()) as Array<{
        symbol: string;
        price: number | null;
        change: number | null;
        changePct: number | null;
      }>;
      const byYahooId = Object.fromEntries(data.map((d) => [d.symbol, d]));
      setPrices(
        WATCH_SYMBOLS.map((sym) => {
          const row = byYahooId[sym.yahooId];
          return {
            ...sym,
            price: row?.price ?? null,
            change: row?.change ?? null,
            changePct: row?.changePct ?? null,
            lastUpdated: new Date(),
          };
        })
      );
      setLastRefresh(new Date());
    } catch {
      // silently fail
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchPrices();
    const id = setInterval(fetchPrices, 30_000);
    return () => clearInterval(id);
  }, [fetchPrices]);

  return { prices, loading, lastRefresh, refetch: fetchPrices };
}

function PriceTicker() {
  const { prices, loading, lastRefresh, refetch } = usePriceFeed();

  return (
    <div className='space-y-1.5'>
      <div className='flex items-center justify-between'>
        <span className='text-[10px] text-[var(--to-text-dim)] font-mono'>
          {lastRefresh
            ? `Updated ${format(lastRefresh, 'HH:mm:ss')}`
            : 'Loading…'}
        </span>
        <button
          onClick={refetch}
          className='text-[var(--to-text-dim)] hover:text-[var(--to-text-secondary)] transition-colors'
        >
          <RefreshCw className={cn('h-3 w-3', loading && 'animate-spin')} />
        </button>
      </div>
      {prices.map((p) => (
        <div
          key={p.symbol}
          className='flex items-center justify-between px-2.5 py-2 rounded-lg border border-[var(--to-border)] bg-[var(--to-surface-raised)]'
        >
          <div>
            <div className='text-[12px] font-semibold font-mono text-[var(--to-text-primary)]'>
              {p.display}
            </div>
          </div>
          <div className='text-right'>
            <div className='text-[12px] font-mono font-bold text-[var(--to-text-primary)]'>
              {p.price != null
                ? p.price.toFixed(
                    p.symbol.includes('JPY')
                      ? 3
                      : p.symbol === 'XAUUSD' ||
                        p.symbol === 'BTCUSD' ||
                        p.symbol.includes('NAS')
                      ? 2
                      : 5
                  )
                : '—'}
            </div>
            {p.changePct != null && (
              <div
                className='text-[10px] font-mono font-semibold flex items-center justify-end gap-0.5'
                style={{ color: p.changePct >= 0 ? '#0ecb81' : '#f6465d' }}
              >
                {p.changePct >= 0 ? (
                  <TrendingUp className='h-2.5 w-2.5' />
                ) : (
                  <TrendingDown className='h-2.5 w-2.5' />
                )}
                {p.changePct >= 0 ? '+' : ''}
                {p.changePct.toFixed(2)}%
              </div>
            )}
          </div>
        </div>
      ))}
    </div>
  );
}

// ── Economic Calendar ─────────────────────────────────────────────────────────

const SAMPLE_EVENTS = [
  {
    time: '08:30',
    currency: 'USD',
    event: 'Non-Farm Payrolls',
    impact: 'high',
  },
  {
    time: '10:00',
    currency: 'USD',
    event: 'ISM Manufacturing PMI',
    impact: 'medium',
  },
  {
    time: '13:30',
    currency: 'GBP',
    event: 'BoE Interest Rate Decision',
    impact: 'high',
  },
  {
    time: '15:00',
    currency: 'EUR',
    event: 'ECB Press Conference',
    impact: 'high',
  },
  { time: '18:00', currency: 'JPY', event: 'Trade Balance', impact: 'low' },
];

function EconomicCalendar() {
  const now = new Date();

  return (
    <div className='space-y-1.5'>
      <div className='text-[10px] text-[var(--to-text-dim)] font-mono mb-2'>
        Today — {format(now, 'MMM dd, yyyy')}
      </div>
      {SAMPLE_EVENTS.map((ev, i) => {
        const isPast = ev.time < format(now, 'HH:mm');
        const impactColor =
          ev.impact === 'high'
            ? '#f6465d'
            : ev.impact === 'medium'
            ? '#f0b90b'
            : '#848e9c';
        return (
          <div
            key={i}
            className={cn(
              'flex items-center gap-2.5 px-2.5 py-2 rounded-lg border transition-opacity',
              isPast
                ? 'opacity-50 border-[var(--to-border)]'
                : 'border-[var(--to-border)] bg-[var(--to-surface-raised)]'
            )}
          >
            <div className='text-[10px] font-mono text-[var(--to-text-dim)] w-10 shrink-0'>
              {ev.time}
            </div>
            <div
              className='h-2 w-2 rounded-full shrink-0'
              style={{ backgroundColor: impactColor }}
              title={`${ev.impact} impact`}
            />
            <div className='text-[10px] font-mono font-semibold text-[var(--to-text-secondary)] w-8 shrink-0'>
              {ev.currency}
            </div>
            <div className='text-[11px] text-[var(--to-text-primary)] truncate flex-1'>
              {ev.event}
            </div>
          </div>
        );
      })}
      <div className='text-[9px] text-[var(--to-text-dim)] text-center mt-2 font-mono'>
        Sample events — connect to a calendar API for live data
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
    const fetchFeed = async () => {
      try {
        // Free RSS-to-JSON proxy
        const url =
          'https://api.rss2json.com/v1/api.json?rss_url=https://feeds.content.dowjones.io/public/rss/mw_realtimeheadlines';
        const res = await fetch(url, { signal: AbortSignal.timeout(5000) });
        const json = await res.json();
        if (json.items) {
          setItems(
            json.items.slice(0, 8).map((item: Record<string, unknown>) => ({
              title: (item.title as string) || '',
              source: (item.author as string) || 'MarketWatch',
              url: (item.link as string) || '#',
              pubDate: (item.pubDate as string) || '',
            }))
          );
        }
      } catch {
        // API unavailable — leave empty
      } finally {
        setLoading(false);
      }
    };
    fetchFeed();
    const id = setInterval(fetchFeed, 5 * 60_000); // every 5 min
    return () => clearInterval(id);
  }, []);

  return { items, loading };
}

function NewsFeed() {
  const { items, loading } = useNewsFeed();

  if (loading) {
    return (
      <div className='space-y-2'>
        {[1, 2, 3].map((i) => (
          <div
            key={i}
            className='h-14 rounded-lg bg-[var(--to-surface-raised)] animate-pulse'
          />
        ))}
      </div>
    );
  }

  if (items.length === 0) {
    return (
      <div className='text-center text-[11px] text-[var(--to-text-dim)] py-6'>
        News feed unavailable. Ensure you have internet access.
      </div>
    );
  }

  return (
    <div className='space-y-2'>
      {items.map((item, i) => (
        <a
          key={i}
          href={item.url}
          target='_blank'
          rel='noopener noreferrer'
          className='block px-2.5 py-2 rounded-lg border border-[var(--to-border)] bg-[var(--to-surface-raised)] hover:border-[var(--to-border)]/70 hover:bg-[var(--to-surface)] transition-colors group'
        >
          <div className='text-[11px] text-[var(--to-text-primary)] leading-snug group-hover:text-[var(--to-text-primary)] line-clamp-2'>
            {item.title}
          </div>
          <div className='flex items-center gap-2 mt-1'>
            <span className='text-[9px] text-[var(--to-text-dim)] font-mono'>
              {item.source}
            </span>
            {item.pubDate && (
              <span className='text-[9px] text-[var(--to-text-dim)] font-mono'>
                · {format(new Date(item.pubDate), 'HH:mm')}
              </span>
            )}
            <ChevronRight className='h-2.5 w-2.5 text-[var(--to-text-dim)] ml-auto' />
          </div>
        </a>
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
    {
      key: 'prices',
      label: 'Prices',
      icon: <TrendingUp className='h-3 w-3' />,
    },
    {
      key: 'calendar',
      label: 'Calendar',
      icon: <Calendar className='h-3 w-3' />,
    },
    { key: 'news', label: 'News', icon: <Rss className='h-3 w-3' /> },
  ];

  return (
    <>
      {/* Backdrop */}
      <div className='fixed inset-0 z-40 bg-black/5' onClick={onClose} />

      {/* Panel */}
      <div
        className='fixed left-[72px] top-[76px] z-50 flex flex-col rounded-xl border border-[var(--to-border)] bg-[var(--to-bg)] shadow-[0_18px_55px_rgba(0,0,0,0.45)]'
        style={{
          width: 320,
          maxHeight: 'min(78vh, 760px)',
        }}
      >
        {/* Header */}
        <div className='flex items-center justify-between px-4 py-3 border-b border-[var(--to-border)] shrink-0'>
          <div className='flex items-center gap-2'>
            <Globe className='h-4 w-4 text-[#0ecb81]' />
            <span className='text-[13px] font-semibold text-[var(--to-text-primary)]'>
              Live Market
            </span>
          </div>
          <button
            onClick={onClose}
            className='text-[var(--to-text-dim)] hover:text-[var(--to-text-secondary)] transition-colors'
          >
            <X className='h-4 w-4' />
          </button>
        </div>

        {/* Tab bar */}
        <div className='flex border-b border-[var(--to-border)] shrink-0 px-1.5 py-1'>
          {tabs.map((t) => (
            <button
              key={t.key}
              onClick={() => setTab(t.key)}
              className={cn(
                'flex-1 flex items-center justify-center gap-1.5 rounded-md py-1.5 text-[11px] font-medium transition-colors border',
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

// ── Trigger button for TopBar ────────────────────────────────────────────────

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
