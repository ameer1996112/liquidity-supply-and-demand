'use client';

/**
 * PropFirmWidget - Real-time FTMO/MyFundedFX compliance tracking
 *
 * Features:
 * - Daily high water mark tracking
 * - Floating + closed PnL
 * - Real-time drawdown gauges
 * - Consistency rule monitoring
 * - Days remaining in challenge
 *
 * Author: Trinity Engine v3.0
 */

import { useEffect, useState } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { AlertTriangle, CheckCircle, Clock } from 'lucide-react';
import { API_BASE_URL } from '@/lib/api';

interface PropFirmMetrics {
  equity: {
    daily_start_balance: number;
    current_equity: number;
    daily_high_water_mark: number;
  };
  daily_pnl: {
    closed: number;
    floating: number;
    total: number;
  };
  drawdown: {
    daily_pct: number;
    daily_limit_pct: number;
    daily_remaining_usd: number;
    trailing_pct: number;
    trailing_limit_pct: number;
  };
  status: {
    daily_loss_breach: boolean;
    drawdown_breach: boolean;
    safe_to_trade: boolean;
    consistency_ok: boolean;
  };
  consistency: {
    best_day_pct: number;
    limit_pct: number;
    status: 'safe' | 'warning' | 'danger' | 'violated';
  };
  days_remaining: number | null;
}

interface PropFirmData {
  status: string;
  account_name: string;
  evaluation_phase: string;
  metrics: PropFirmMetrics;
}

export function PropFirmWidget() {
  const [data, setData] = useState<PropFirmData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const fetchMetrics = async () => {
      try {
        const res = await fetch(`${API_BASE_URL}/api/prop-firm/metrics`);
        if (!res.ok) {
          throw new Error(`HTTP ${res.status}`);
        }
        const json = await res.json();
        setData(json);
        setError(null);
      } catch (err) {
        console.error('Failed to fetch prop firm metrics:', err);
        setError(err instanceof Error ? err.message : 'Unknown error');
      } finally {
        setLoading(false);
      }
    };

    fetchMetrics();
    const interval = setInterval(fetchMetrics, 10000); // Update every 10 seconds
    return () => clearInterval(interval);
  }, []);

  if (loading) {
    return (
      <Card className='col-span-2'>
        <CardHeader>
          <CardTitle className='flex items-center gap-2'>
            🏆 Prop Firm Challenge Tracker
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className='flex items-center justify-center py-8'>
            <div className='text-muted-foreground'>Loading metrics...</div>
          </div>
        </CardContent>
      </Card>
    );
  }

  if (error || !data) {
    return (
      <Card className='col-span-2'>
        <CardHeader>
          <CardTitle>🏆 Prop Firm Challenge Tracker</CardTitle>
        </CardHeader>
        <CardContent>
          <Alert variant='destructive'>
            <AlertTriangle className='h-4 w-4' />
            <AlertDescription>
              Failed to load metrics: {error || 'Unknown error'}
            </AlertDescription>
          </Alert>
        </CardContent>
      </Card>
    );
  }

  const { metrics } = data;
  const isDangerZone =
    (metrics.drawdown?.daily_pct ?? 0) > 3.5 ||
    (metrics.drawdown?.trailing_pct ?? 0) > 7.0;
  const isWarningZone =
    (metrics.drawdown?.daily_pct ?? 0) > 2.5 ||
    (metrics.drawdown?.trailing_pct ?? 0) > 5.0;

  // Determine overall status
  let overallStatus: 'danger' | 'warning' | 'ok' = 'ok';
  if (!metrics.status.safe_to_trade || isDangerZone) {
    overallStatus = 'danger';
  } else if (isWarningZone) {
    overallStatus = 'warning';
  }

  return (
    <Card className='col-span-2'>
      <CardHeader>
        <CardTitle className='flex items-center justify-between'>
          <span className='flex items-center gap-2'>
            🏆 Prop Firm Challenge Tracker
            <span className='text-sm font-normal text-muted-foreground'>
              ({data.evaluation_phase.toUpperCase()})
            </span>
          </span>
          {metrics.status.safe_to_trade ? (
            <CheckCircle className='h-5 w-5 text-green-500' />
          ) : (
            <AlertTriangle className='h-5 w-5 text-red-500' />
          )}
        </CardTitle>
      </CardHeader>
      <CardContent className='space-y-4'>
        {/* Status Alert */}
        {!metrics.status.safe_to_trade && (
          <Alert variant='destructive'>
            <AlertTriangle className='h-4 w-4' />
            <AlertDescription>
              {metrics.status.daily_loss_breach &&
                '🚨 DAILY LOSS LIMIT BREACHED - Trading Halted'}
              {metrics.status.drawdown_breach &&
                '🚨 MAX DRAWDOWN BREACHED - Challenge Failed'}
            </AlertDescription>
          </Alert>
        )}

        {overallStatus === 'danger' && metrics.status.safe_to_trade && (
          <Alert variant='destructive'>
            <AlertTriangle className='h-4 w-4' />
            <AlertDescription>
              ⚠️ DANGER ZONE: Approaching daily limit (
              {(metrics.drawdown?.daily_pct ?? 0).toFixed(2)}%)
            </AlertDescription>
          </Alert>
        )}

        {overallStatus === 'warning' && (
          <Alert>
            <AlertTriangle className='h-4 w-4' />
            <AlertDescription>
              ⚠️ Warning: Elevated drawdown level
            </AlertDescription>
          </Alert>
        )}

        {/* Equity Status */}
        <div className='grid grid-cols-4 gap-4'>
          <div>
            <p className='text-sm text-muted-foreground'>Starting Balance</p>
            <p className='text-xl font-bold'>
              $
              {(metrics.equity?.daily_start_balance ?? 0).toLocaleString('en-US', {
                minimumFractionDigits: 2,
                maximumFractionDigits: 2,
              })}
            </p>
          </div>
          <div>
            <p className='text-sm text-muted-foreground'>Current Equity</p>
            <p className='text-xl font-bold'>
              $
              {(metrics.equity?.current_equity ?? 0).toLocaleString('en-US', {
                minimumFractionDigits: 2,
                maximumFractionDigits: 2,
              })}
            </p>
          </div>
          <div>
            <p className='text-sm text-muted-foreground'>Daily PnL</p>
            <p
              className={`text-xl font-bold ${(metrics.daily_pnl?.total ?? 0) >= 0 ? 'text-green-500' : 'text-red-500'}`}
            >
              {(metrics.daily_pnl?.total ?? 0) >= 0 ? '+' : ''}$
              {(metrics.daily_pnl?.total ?? 0).toLocaleString('en-US', {
                minimumFractionDigits: 2,
                maximumFractionDigits: 2,
              })}
            </p>
            <p className='text-xs text-muted-foreground'>
              Closed: ${(metrics.daily_pnl?.closed ?? 0).toFixed(2)} | Floating: $
              {(metrics.daily_pnl?.floating ?? 0).toFixed(2)}
            </p>
          </div>
          {metrics.days_remaining !== null && (
            <div>
              <p className='text-sm text-muted-foreground'>Days Remaining</p>
              <p className='text-xl font-bold flex items-center gap-1'>
                <Clock className='h-4 w-4' />
                {metrics.days_remaining}
              </p>
            </div>
          )}
        </div>

        {/* Drawdown Gauges */}
        <div className='space-y-3'>
          {/* Daily Drawdown */}
          <div>
            <div className='flex justify-between text-sm mb-1'>
              <span className='font-medium'>Daily Drawdown</span>
              <span className='font-bold'>
                {(metrics.drawdown?.daily_pct ?? 0).toFixed(2)}% /{' '}
                {metrics.drawdown?.daily_limit_pct ?? 0}%
              </span>
            </div>
            <div className='w-full bg-gray-200 rounded-full h-4 overflow-hidden'>
              <div
                className={`h-4 rounded-full transition-all duration-300 ${
                  (metrics.drawdown?.daily_pct ?? 0) > 4.0
                    ? 'bg-red-500'
                    : (metrics.drawdown?.daily_pct ?? 0) > 3.0
                      ? 'bg-orange-500'
                      : (metrics.drawdown?.daily_pct ?? 0) > 2.0
                        ? 'bg-yellow-500'
                        : 'bg-green-500'
                }`}
                style={{
                  width: `${Math.min(((metrics.drawdown?.daily_pct ?? 0) / (metrics.drawdown?.daily_limit_pct ?? 1)) * 100, 100)}%`,
                }}
              />
            </div>
            <p className='text-xs text-muted-foreground mt-1'>
              $
              {(metrics.drawdown?.daily_remaining_usd ?? 0).toLocaleString('en-US', {
                minimumFractionDigits: 2,
                maximumFractionDigits: 2,
              })}{' '}
              remaining before breach
            </p>
          </div>

          {/* Trailing Drawdown */}
          <div>
            <div className='flex justify-between text-sm mb-1'>
              <span className='font-medium'>Trailing Drawdown</span>
              <span className='font-bold'>
                {(metrics.drawdown?.trailing_pct ?? 0).toFixed(2)}% /{' '}
                {metrics.drawdown?.trailing_limit_pct ?? 0}%
              </span>
            </div>
            <div className='w-full bg-gray-200 rounded-full h-4 overflow-hidden'>
              <div
                className={`h-4 rounded-full transition-all duration-300 ${
                  (metrics.drawdown?.trailing_pct ?? 0) > 8.0
                    ? 'bg-red-500'
                    : (metrics.drawdown?.trailing_pct ?? 0) > 6.0
                      ? 'bg-orange-500'
                      : (metrics.drawdown?.trailing_pct ?? 0) > 4.0
                        ? 'bg-yellow-500'
                        : 'bg-green-500'
                }`}
                style={{
                  width: `${Math.min(((metrics.drawdown?.trailing_pct ?? 0) / (metrics.drawdown?.trailing_limit_pct ?? 1)) * 100, 100)}%`,
                }}
              />
            </div>
          </div>

          {/* Consistency */}
          <div>
            <div className='flex justify-between text-sm mb-1'>
              <span className='font-medium'>Consistency (Best Day %)</span>
              <span className='font-bold'>
                {(metrics.consistency?.best_day_pct ?? 0).toFixed(1)}% /{' '}
                {metrics.consistency?.limit_pct ?? 0}%
              </span>
            </div>
            <div className='w-full bg-gray-200 rounded-full h-4 overflow-hidden'>
              <div
                className={`h-4 rounded-full transition-all duration-300 ${
                  (metrics.consistency?.status ?? 'safe') === 'violated'
                    ? 'bg-red-500'
                    : (metrics.consistency?.status ?? 'safe') === 'danger'
                      ? 'bg-orange-500'
                      : (metrics.consistency?.status ?? 'safe') === 'warning'
                        ? 'bg-yellow-500'
                        : 'bg-green-500'
                }`}
                style={{
                  width: `${Math.min(((metrics.consistency?.best_day_pct ?? 0) / (metrics.consistency?.limit_pct ?? 1)) * 100, 100)}%`,
                }}
              />
            </div>
            <p className='text-xs text-muted-foreground mt-1'>
              FTMO Rule: Best day cannot exceed {metrics.consistency.limit_pct}%
              of total profit
            </p>
          </div>
        </div>

        {/* Status Summary */}
        <div className='flex items-center justify-between pt-2 border-t'>
          <div className='text-sm text-muted-foreground'>Status:</div>
          <div className='flex gap-2'>
            <span
              className={`px-2 py-1 rounded text-xs font-medium ${
                metrics.status.safe_to_trade
                  ? 'bg-green-100 text-green-800'
                  : 'bg-red-100 text-red-800'
              }`}
            >
              {metrics.status.safe_to_trade
                ? '✅ Safe to Trade'
                : '🚨 Trading Halted'}
            </span>
            <span
              className={`px-2 py-1 rounded text-xs font-medium ${
                metrics.status.consistency_ok
                  ? 'bg-green-100 text-green-800'
                  : 'bg-orange-100 text-orange-800'
              }`}
            >
              {metrics.status.consistency_ok
                ? '✅ Consistent'
                : '⚠️ Consistency Risk'}
            </span>
          </div>
        </div>
      </CardContent>
    </Card>
  );
}
