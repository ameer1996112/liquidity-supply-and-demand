'use client';

import { useState } from 'react';
import {
  useRiskDashboard,
  useCorrelationMatrix,
  useRiskContribution,
  useSectorExposure,
} from '@/hooks/usePortfolioRisk';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Skeleton } from '@/components/ui/skeleton';
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  PieChart,
  Pie,
  Cell,
} from 'recharts';
import {
  TrendingDown,
  DollarSign,
  Activity,
  AlertTriangle,
} from 'lucide-react';
import { cn } from '@/lib/utils';
import {
  getVarUtilizationColor,
  getSectorStatusColor,
} from '@/types/portfolio';

const LOOKBACK_OPTIONS = [
  { label: '7d', days: 7 },
  { label: '30d', days: 30 },
  { label: '90d', days: 90 },
];

const PIE_COLORS = [
  '#6366f1',
  '#10b981',
  '#f59e0b',
  '#8b5cf6',
  '#ef4444',
  '#334155',
];

export default function PortfolioRiskPage() {
  const [lookbackDays, setLookbackDays] = useState(30);

  const { data: dashboard, isLoading: dashboardLoading } =
    useRiskDashboard(lookbackDays);
  const { data: correlationMatrix, isLoading: corrLoading } =
    useCorrelationMatrix(lookbackDays);
  const { data: riskContribution, isLoading: contribLoading } =
    useRiskContribution(lookbackDays);
  const { data: sectorExposure, isLoading: sectorLoading } =
    useSectorExposure();

  const hasData = dashboard && dashboard.position_count > 0;

  return (
    <div className='space-y-4'>
      {/* Header */}
      <div className='flex items-center justify-between'>
        <div>
          <h1 className='page-title text-lg font-semibold'>Portfolio Risk</h1>
          <p className='page-subtitle mt-0.5 text-xs'>
            Value-at-Risk, Correlation Analysis & Sector Exposure
          </p>
        </div>

        {/* Lookback Period Selector */}
        <div className='surface-soft flex items-center gap-1 rounded-md p-1'>
          {LOOKBACK_OPTIONS.map((option) => (
            <button
              key={option.days}
              onClick={() => setLookbackDays(option.days)}
              className={cn(
                'font-mono text-[11px] px-2.5 py-1 rounded transition-colors',
                lookbackDays === option.days
                  ? 'bg-indigo-600/20 text-indigo-300'
                  : 'text-slate-500 hover:text-slate-300'
              )}
            >
              {option.label}
            </button>
          ))}
        </div>
      </div>

      {/* Summary Cards */}
      <div className='grid grid-cols-1 gap-4 md:grid-cols-4'>
        <Card className='tv-card'>
          <CardHeader className='pb-2'>
            <CardTitle className='flex items-center gap-1.5 text-xs text-slate-500'>
              <TrendingDown className='h-3.5 w-3.5' />
              Portfolio VaR (95%)
            </CardTitle>
          </CardHeader>
          <CardContent>
            {dashboardLoading ? (
              <Skeleton className='h-6 w-20 bg-slate-800/60' />
            ) : (
              <div>
                <div
                  className={cn(
                    'text-2xl font-bold',
                    hasData
                      ? getVarUtilizationColor(
                          dashboard?.var_utilization_pct || 0
                        )
                      : 'text-slate-100'
                  )}
                >
                  ${Math.abs(dashboard?.var_95_1d || 0).toFixed(0)}
                </div>
                <div className='mt-1 text-xs text-slate-500'>
                  {dashboard?.var_utilization_pct.toFixed(0)}% of limit
                </div>
              </div>
            )}
          </CardContent>
        </Card>

        <Card className='tv-card'>
          <CardHeader className='pb-2'>
            <CardTitle className='flex items-center gap-1.5 text-xs text-slate-500'>
              <DollarSign className='h-3.5 w-3.5' />
              CVaR (Expected Shortfall)
            </CardTitle>
          </CardHeader>
          <CardContent>
            {dashboardLoading ? (
              <Skeleton className='h-6 w-20 bg-slate-800/60' />
            ) : (
              <div>
                <div className='text-2xl font-bold text-slate-100'>
                  ${Math.abs(dashboard?.cvar_95 || 0).toFixed(0)}
                </div>
                <div className='mt-1 text-xs text-slate-500'>
                  Worst-case 5% scenario
                </div>
              </div>
            )}
          </CardContent>
        </Card>

        <Card className='tv-card'>
          <CardHeader className='pb-2'>
            <CardTitle className='flex items-center gap-1.5 text-xs text-slate-500'>
              <Activity className='h-3.5 w-3.5' />
              Portfolio Volatility
            </CardTitle>
          </CardHeader>
          <CardContent>
            {dashboardLoading ? (
              <Skeleton className='h-6 w-20 bg-slate-800/60' />
            ) : (
              <div>
                <div className='text-2xl font-bold text-slate-100'>
                  {dashboard?.portfolio_volatility.toFixed(1)}%
                </div>
                <div className='mt-1 text-xs text-slate-500'>Annualized</div>
              </div>
            )}
          </CardContent>
        </Card>

        <Card className='tv-card'>
          <CardHeader className='pb-2'>
            <CardTitle className='flex items-center gap-1.5 text-xs text-slate-500'>
              <AlertTriangle className='h-3.5 w-3.5' />
              Avg Correlation
            </CardTitle>
          </CardHeader>
          <CardContent>
            {dashboardLoading ? (
              <Skeleton className='h-6 w-20 bg-slate-800/60' />
            ) : (
              <div>
                <div
                  className={cn(
                    'text-2xl font-bold',
                    (dashboard?.correlation_avg || 0) > 0.7
                      ? 'text-amber-400'
                      : 'text-slate-100'
                  )}
                >
                  {dashboard?.correlation_avg.toFixed(2)}
                </div>
                <div className='mt-1 text-xs text-slate-500'>
                  Max: {dashboard?.max_correlation.toFixed(2)}
                </div>
              </div>
            )}
          </CardContent>
        </Card>
      </div>

      {/* Risk Contribution Pie Chart */}
      <div className='grid grid-cols-1 gap-4 md:grid-cols-2'>
        <Card className='tv-card'>
          <CardHeader>
            <CardTitle className='text-sm font-medium text-slate-100'>
              VaR Contribution by Position
            </CardTitle>
          </CardHeader>
          <CardContent>
            {contribLoading ? (
              <Skeleton className='h-[300px] w-full bg-slate-800/60' />
            ) : riskContribution && riskContribution.length > 0 ? (
              <ResponsiveContainer width='100%' height={300}>
                <PieChart>
                  <Pie
                    data={riskContribution.map((item, idx) => ({
                      name: item.symbol,
                      value: Math.abs(item.var_contribution_pct),
                    }))}
                    cx='50%'
                    cy='50%'
                    labelLine={false}
                    label={({
                      cx = 0,
                      cy = 0,
                      midAngle = 0,
                      innerRadius = 0,
                      outerRadius = 0,
                      percent = 0,
                    }) => {
                      const radius =
                        innerRadius + (outerRadius - innerRadius) * 0.5;
                      const angle = midAngle * (Math.PI / 180);
                      const x = cx + radius * Math.cos(-angle);
                      const y = cy + radius * Math.sin(-angle);
                      return (
                        <text
                          x={x}
                          y={y}
                          fill='white'
                          textAnchor={x > cx ? 'start' : 'end'}
                          dominantBaseline='central'
                          style={{ fontSize: 11 }}
                        >
                          {`${(percent * 100).toFixed(0)}%`}
                        </text>
                      );
                    }}
                    outerRadius={100}
                    fill='#8884d8'
                    dataKey='value'
                  >
                    {riskContribution.map((entry, index) => (
                      <Cell
                        key={`cell-${index}`}
                        fill={PIE_COLORS[index % PIE_COLORS.length]}
                      />
                    ))}
                  </Pie>
                  <Tooltip
                    contentStyle={{
                      backgroundColor: '#0f172a',
                      border: '1px solid #334155',
                      borderRadius: '4px',
                      fontSize: 11,
                    }}
                  />
                </PieChart>
              </ResponsiveContainer>
            ) : (
              <div className='flex h-[300px] items-center justify-center text-sm text-slate-500'>
                No active positions
              </div>
            )}
          </CardContent>
        </Card>

        {/* Sector Exposure */}
        <Card className='tv-card'>
          <CardHeader>
            <CardTitle className='text-sm font-medium text-slate-100'>
              Sector Exposure
            </CardTitle>
          </CardHeader>
          <CardContent>
            {sectorLoading ? (
              <Skeleton className='h-[300px] w-full bg-slate-800/60' />
            ) : sectorExposure && sectorExposure.length > 0 ? (
              <ResponsiveContainer width='100%' height={300}>
                <BarChart data={sectorExposure}>
                  <CartesianGrid strokeDasharray='3 3' stroke='#334155' />
                  <XAxis
                    dataKey='sector'
                    stroke='#64748b'
                    style={{ fontSize: 10 }}
                    angle={-45}
                    textAnchor='end'
                    height={80}
                  />
                  <YAxis
                    label={{
                      value: 'Exposure %',
                      angle: -90,
                      position: 'insideLeft',
                      style: { fontSize: 11, fill: '#64748b' },
                    }}
                    stroke='#64748b'
                    style={{ fontSize: 11 }}
                  />
                  <Tooltip
                    contentStyle={{
                      backgroundColor: '#0f172a',
                      border: '1px solid #334155',
                      borderRadius: '4px',
                      fontSize: 11,
                    }}
                  />
                  <Bar
                    dataKey='exposure_pct'
                    fill='#10b981'
                    radius={[4, 4, 0, 0]}
                  />
                  <Bar
                    dataKey='limit_pct'
                    fill='#475569'
                    radius={[4, 4, 0, 0]}
                    opacity={0.3}
                  />
                </BarChart>
              </ResponsiveContainer>
            ) : (
              <div className='flex h-[300px] items-center justify-center text-sm text-slate-500'>
                No sector exposure data
              </div>
            )}
          </CardContent>
        </Card>
      </div>

      {/* Active Positions Table */}
      {hasData && (
        <Card className='tv-card'>
          <CardHeader>
            <CardTitle className='text-sm font-medium text-slate-100'>
              Active Positions
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className='overflow-x-auto'>
              <table className='w-full text-xs'>
                <thead>
                  <tr className='border-b border-slate-700'>
                    <th className='px-2 py-2 text-left font-mono text-slate-500'>
                      Symbol
                    </th>
                    <th className='px-2 py-2 text-left font-mono text-slate-500'>
                      Side
                    </th>
                    <th className='px-2 py-2 text-right font-mono text-slate-500'>
                      Size
                    </th>
                    <th className='px-2 py-2 text-right font-mono text-slate-500'>
                      Entry
                    </th>
                    <th className='px-2 py-2 text-right font-mono text-slate-500'>
                      Current
                    </th>
                    <th className='px-2 py-2 text-right font-mono text-slate-500'>
                      P&L
                    </th>
                    <th className='px-2 py-2 text-right font-mono text-slate-500'>
                      Notional
                    </th>
                  </tr>
                </thead>
                <tbody>
                  {dashboard?.positions.map((pos, idx) => (
                    <tr key={idx} className='border-b border-slate-700/50'>
                      <td className='px-2 py-2 font-mono text-slate-300'>
                        {pos.symbol}
                      </td>
                      <td className='px-2 py-2'>
                        <span
                          className={cn(
                            'font-mono text-[10px] px-1.5 py-0.5 rounded',
                            pos.side.toLowerCase() === 'long'
                              ? 'bg-emerald-500/15 text-emerald-400'
                              : 'bg-red-500/15 text-red-400'
                          )}
                        >
                          {pos.side.toUpperCase()}
                        </span>
                      </td>
                      <td className='px-2 py-2 text-right font-mono text-slate-300'>
                        {pos.size.toFixed(2)}
                      </td>
                      <td className='px-2 py-2 text-right font-mono text-slate-400'>
                        {pos.entry_price.toFixed(5)}
                      </td>
                      <td className='px-2 py-2 text-right font-mono text-slate-400'>
                        {pos.current_price.toFixed(5)}
                      </td>
                      <td
                        className={cn(
                          'py-2 px-2 text-right font-mono',
                          pos.pnl_usd >= 0 ? 'text-emerald-400' : 'text-red-400'
                        )}
                      >
                        ${pos.pnl_usd.toFixed(2)}
                      </td>
                      <td className='px-2 py-2 text-right font-mono text-slate-400'>
                        ${pos.notional_value.toFixed(0)}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </CardContent>
        </Card>
      )}
    </div>
  );
}
