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
import { TrendingDown, DollarSign, Activity, AlertTriangle } from 'lucide-react';
import { cn } from '@/lib/utils';
import { getVarUtilizationColor, getSectorStatusColor } from '@/types/portfolio';

const LOOKBACK_OPTIONS = [
  { label: '7d', days: 7 },
  { label: '30d', days: 30 },
  { label: '90d', days: 90 },
];

const PIE_COLORS = [
  '#2962ff',
  '#26a69a',
  '#ff6d00',
  '#ab47bc',
  '#ec407a',
  '#5c6bc0',
];

export default function PortfolioRiskPage() {
  const [lookbackDays, setLookbackDays] = useState(30);

  const { data: dashboard, isLoading: dashboardLoading } = useRiskDashboard(lookbackDays);
  const { data: correlationMatrix, isLoading: corrLoading } = useCorrelationMatrix(lookbackDays);
  const { data: riskContribution, isLoading: contribLoading } = useRiskContribution(lookbackDays);
  const { data: sectorExposure, isLoading: sectorLoading } = useSectorExposure();

  const hasData = dashboard && dashboard.position_count > 0;

  return (
    <div className="space-y-6 p-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-lg font-semibold text-zinc-100">Portfolio Risk</h1>
          <p className="text-xs text-zinc-500 mt-1">
            Value-at-Risk, Correlation Analysis & Sector Exposure
          </p>
        </div>

        {/* Lookback Period Selector */}
        <div className="flex items-center gap-1 bg-[#1e222d] border border-[#2a2e39] rounded-md p-1">
          {LOOKBACK_OPTIONS.map((option) => (
            <button
              key={option.days}
              onClick={() => setLookbackDays(option.days)}
              className={cn(
                'font-mono text-[11px] px-2.5 py-1 rounded transition-colors',
                lookbackDays === option.days
                  ? 'bg-[#2a2e39] text-zinc-200'
                  : 'text-zinc-500 hover:text-zinc-300'
              )}
            >
              {option.label}
            </button>
          ))}
        </div>
      </div>

      {/* Summary Cards */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        <Card className="bg-[#1e222d] border-[#2a2e39]">
          <CardHeader className="pb-2">
            <CardTitle className="text-xs text-zinc-500 flex items-center gap-1.5">
              <TrendingDown className="h-3.5 w-3.5" />
              Portfolio VaR (95%)
            </CardTitle>
          </CardHeader>
          <CardContent>
            {dashboardLoading ? (
              <Skeleton className="h-6 w-20" />
            ) : (
              <div>
                <div
                  className={cn(
                    'text-2xl font-bold',
                    hasData
                      ? getVarUtilizationColor(dashboard?.var_utilization_pct || 0)
                      : 'text-zinc-100'
                  )}
                >
                  ${Math.abs(dashboard?.var_95_1d || 0).toFixed(0)}
                </div>
                <div className="text-xs text-zinc-500 mt-1">
                  {dashboard?.var_utilization_pct.toFixed(0)}% of limit
                </div>
              </div>
            )}
          </CardContent>
        </Card>

        <Card className="bg-[#1e222d] border-[#2a2e39]">
          <CardHeader className="pb-2">
            <CardTitle className="text-xs text-zinc-500 flex items-center gap-1.5">
              <DollarSign className="h-3.5 w-3.5" />
              CVaR (Expected Shortfall)
            </CardTitle>
          </CardHeader>
          <CardContent>
            {dashboardLoading ? (
              <Skeleton className="h-6 w-20" />
            ) : (
              <div>
                <div className="text-2xl font-bold text-zinc-100">
                  ${Math.abs(dashboard?.cvar_95 || 0).toFixed(0)}
                </div>
                <div className="text-xs text-zinc-500 mt-1">
                  Worst-case 5% scenario
                </div>
              </div>
            )}
          </CardContent>
        </Card>

        <Card className="bg-[#1e222d] border-[#2a2e39]">
          <CardHeader className="pb-2">
            <CardTitle className="text-xs text-zinc-500 flex items-center gap-1.5">
              <Activity className="h-3.5 w-3.5" />
              Portfolio Volatility
            </CardTitle>
          </CardHeader>
          <CardContent>
            {dashboardLoading ? (
              <Skeleton className="h-6 w-20" />
            ) : (
              <div>
                <div className="text-2xl font-bold text-zinc-100">
                  {dashboard?.portfolio_volatility.toFixed(1)}%
                </div>
                <div className="text-xs text-zinc-500 mt-1">Annualized</div>
              </div>
            )}
          </CardContent>
        </Card>

        <Card className="bg-[#1e222d] border-[#2a2e39]">
          <CardHeader className="pb-2">
            <CardTitle className="text-xs text-zinc-500 flex items-center gap-1.5">
              <AlertTriangle className="h-3.5 w-3.5" />
              Avg Correlation
            </CardTitle>
          </CardHeader>
          <CardContent>
            {dashboardLoading ? (
              <Skeleton className="h-6 w-20" />
            ) : (
              <div>
                <div
                  className={cn(
                    'text-2xl font-bold',
                    (dashboard?.correlation_avg || 0) > 0.7
                      ? 'text-yellow-500'
                      : 'text-zinc-100'
                  )}
                >
                  {dashboard?.correlation_avg.toFixed(2)}
                </div>
                <div className="text-xs text-zinc-500 mt-1">
                  Max: {dashboard?.max_correlation.toFixed(2)}
                </div>
              </div>
            )}
          </CardContent>
        </Card>
      </div>

      {/* Risk Contribution Pie Chart */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <Card className="bg-[#1e222d] border-[#2a2e39]">
          <CardHeader>
            <CardTitle className="text-sm font-medium text-zinc-100">
              VaR Contribution by Position
            </CardTitle>
          </CardHeader>
          <CardContent>
            {contribLoading ? (
              <Skeleton className="h-[300px] w-full" />
            ) : riskContribution && riskContribution.length > 0 ? (
              <ResponsiveContainer width="100%" height={300}>
                <PieChart>
                  <Pie
                    data={riskContribution.map((item, idx) => ({
                      name: item.symbol,
                      value: Math.abs(item.var_contribution_pct),
                    }))}
                    cx="50%"
                    cy="50%"
                    labelLine={false}
                    label={({
                      cx = 0,
                      cy = 0,
                      midAngle = 0,
                      innerRadius = 0,
                      outerRadius = 0,
                      percent = 0,
                    }) => {
                      const radius = innerRadius + (outerRadius - innerRadius) * 0.5;
                      const angle = midAngle * (Math.PI / 180);
                      const x = cx + radius * Math.cos(-angle);
                      const y = cy + radius * Math.sin(-angle);
                      return (
                        <text
                          x={x}
                          y={y}
                          fill="white"
                          textAnchor={x > cx ? 'start' : 'end'}
                          dominantBaseline="central"
                          style={{ fontSize: 11 }}
                        >
                          {`${(percent * 100).toFixed(0)}%`}
                        </text>
                      );
                    }}
                    outerRadius={100}
                    fill="#8884d8"
                    dataKey="value"
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
                      backgroundColor: '#131722',
                      border: '1px solid #2a2e39',
                      borderRadius: '4px',
                      fontSize: 11,
                    }}
                  />
                </PieChart>
              </ResponsiveContainer>
            ) : (
              <div className="flex items-center justify-center h-[300px] text-zinc-500 text-sm">
                No active positions
              </div>
            )}
          </CardContent>
        </Card>

        {/* Sector Exposure */}
        <Card className="bg-[#1e222d] border-[#2a2e39]">
          <CardHeader>
            <CardTitle className="text-sm font-medium text-zinc-100">
              Sector Exposure
            </CardTitle>
          </CardHeader>
          <CardContent>
            {sectorLoading ? (
              <Skeleton className="h-[300px] w-full" />
            ) : sectorExposure && sectorExposure.length > 0 ? (
              <ResponsiveContainer width="100%" height={300}>
                <BarChart data={sectorExposure}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#2a2e39" />
                  <XAxis
                    dataKey="sector"
                    stroke="#6b7280"
                    style={{ fontSize: 10 }}
                    angle={-45}
                    textAnchor="end"
                    height={80}
                  />
                  <YAxis
                    label={{
                      value: 'Exposure %',
                      angle: -90,
                      position: 'insideLeft',
                      style: { fontSize: 11, fill: '#6b7280' },
                    }}
                    stroke="#6b7280"
                    style={{ fontSize: 11 }}
                  />
                  <Tooltip
                    contentStyle={{
                      backgroundColor: '#131722',
                      border: '1px solid #2a2e39',
                      borderRadius: '4px',
                      fontSize: 11,
                    }}
                  />
                  <Bar dataKey="exposure_pct" fill="#26a69a" radius={[4, 4, 0, 0]} />
                  <Bar
                    dataKey="limit_pct"
                    fill="#4a5568"
                    radius={[4, 4, 0, 0]}
                    opacity={0.3}
                  />
                </BarChart>
              </ResponsiveContainer>
            ) : (
              <div className="flex items-center justify-center h-[300px] text-zinc-500 text-sm">
                No sector exposure data
              </div>
            )}
          </CardContent>
        </Card>
      </div>

      {/* Active Positions Table */}
      {hasData && (
        <Card className="bg-[#1e222d] border-[#2a2e39]">
          <CardHeader>
            <CardTitle className="text-sm font-medium text-zinc-100">
              Active Positions
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="overflow-x-auto">
              <table className="w-full text-xs">
                <thead>
                  <tr className="border-b border-[#2a2e39]">
                    <th className="text-left py-2 px-2 text-zinc-500 font-mono">Symbol</th>
                    <th className="text-left py-2 px-2 text-zinc-500 font-mono">Side</th>
                    <th className="text-right py-2 px-2 text-zinc-500 font-mono">Size</th>
                    <th className="text-right py-2 px-2 text-zinc-500 font-mono">Entry</th>
                    <th className="text-right py-2 px-2 text-zinc-500 font-mono">Current</th>
                    <th className="text-right py-2 px-2 text-zinc-500 font-mono">P&L</th>
                    <th className="text-right py-2 px-2 text-zinc-500 font-mono">Notional</th>
                  </tr>
                </thead>
                <tbody>
                  {dashboard?.positions.map((pos, idx) => (
                    <tr key={idx} className="border-b border-[#2a2e39]/50">
                      <td className="py-2 px-2 font-mono text-zinc-300">{pos.symbol}</td>
                      <td className="py-2 px-2">
                        <span
                          className={cn(
                            'font-mono text-[10px] px-1.5 py-0.5 rounded',
                            pos.side.toLowerCase() === 'long'
                              ? 'bg-[#26a69a]/15 text-[#26a69a]'
                              : 'bg-[#ef5350]/15 text-[#ef5350]'
                          )}
                        >
                          {pos.side.toUpperCase()}
                        </span>
                      </td>
                      <td className="py-2 px-2 text-right font-mono text-zinc-300">
                        {pos.size.toFixed(2)}
                      </td>
                      <td className="py-2 px-2 text-right font-mono text-zinc-400">
                        {pos.entry_price.toFixed(5)}
                      </td>
                      <td className="py-2 px-2 text-right font-mono text-zinc-400">
                        {pos.current_price.toFixed(5)}
                      </td>
                      <td
                        className={cn(
                          'py-2 px-2 text-right font-mono',
                          pos.pnl_usd >= 0 ? 'text-[#26a69a]' : 'text-[#ef5350]'
                        )}
                      >
                        ${pos.pnl_usd.toFixed(2)}
                      </td>
                      <td className="py-2 px-2 text-right font-mono text-zinc-400">
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
