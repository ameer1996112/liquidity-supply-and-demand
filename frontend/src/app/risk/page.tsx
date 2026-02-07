'use client';

import { useCallback, useMemo } from 'react';
import { Shield, Gauge, Table2 } from 'lucide-react';
import { RiskKnob } from '@/components/risk/RiskKnob';
import { GuardRailToggle } from '@/components/risk/GuardRailToggle';
import { SymbolOverrideTable } from '@/components/risk/SymbolOverrideTable';
import {
  useRiskSettings,
  useUpdateRiskSetting,
} from '@/hooks/useRiskConfig';
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from '@/components/ui/card';

export default function RiskControlPage() {
  const { data, isLoading, error } = useRiskSettings();
  const updateSetting = useUpdateRiskSetting();

  const riskPercent = useMemo(() => {
    if (!data?.settings) return 1;
    const v = data.settings.risk_percent;
    return typeof v === 'number' ? v : Number(v) || 1;
  }, [data?.settings]);

  const portfolioVarEnabled = useMemo(() => {
    if (!data?.settings) return true;
    const v = data.settings.portfolio_var_enabled;
    return typeof v === 'boolean' ? v : Boolean(v);
  }, [data?.settings]);

  const handleRiskChange = useCallback(
    (value: number) => {
      updateSetting.mutate({
        settingKey: 'risk_percent',
        value,
        changeReason: 'Risk Control Center',
      });
    },
    [updateSetting]
  );

  const guardRailItems = useMemo(
    () => [
      {
        id: 'max_drawdown',
        label: 'Max Drawdown Guard',
        description: 'Portfolio VaR limit',
        enabled: portfolioVarEnabled,
        settingKey: 'portfolio_var_enabled',
      },
      {
        id: 'news_filter',
        label: 'News Filter',
        description: 'Reduce risk around high-impact news',
        enabled: false,
        settingKey: undefined as string | undefined,
      },
      {
        id: 'weekend_protection',
        label: 'Weekend Protection',
        description: 'Tighten risk over weekends',
        enabled: false,
        settingKey: undefined as string | undefined,
      },
    ],
    [portfolioVarEnabled]
  );

  const handleGuardToggle = useCallback(
    (id: string, enabled: boolean, settingKey?: string) => {
      if (!settingKey) return;
      updateSetting.mutate({
        settingKey,
        value: enabled,
        changeReason: `Guard rail: ${id}`,
      });
    },
    [updateSetting]
  );

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-lg font-semibold text-zinc-100">
          Risk Control Center
        </h1>
        <p className="text-sm text-zinc-500 mt-0.5">
          Adjust risk parameters live without restarting the bot.
        </p>
      </div>

      {error && (
        <div className="rounded-lg border border-amber-500/30 bg-amber-500/5 px-4 py-3 text-sm text-amber-600">
          Failed to load risk settings. Ensure the backend API is running and
          NEXT_PUBLIC_API_URL is set.
        </div>
      )}

      <div className="grid gap-6 md:grid-cols-2">
        {/* Risk per trade knob */}
        <Card className="border-[#2a2e39] bg-[#1e222d]/50">
          <CardHeader className="pb-2">
            <div className="flex items-center gap-2">
              <Gauge className="h-4 w-4 text-emerald-500" />
              <CardTitle className="text-sm font-medium text-zinc-100">
                Risk per trade
              </CardTitle>
            </div>
            <CardDescription className="text-[11px] text-zinc-500">
              0.1% – 5%. Applies globally unless overridden per symbol.
            </CardDescription>
          </CardHeader>
          <CardContent>
            {isLoading ? (
              <div className="flex h-40 items-center justify-center text-zinc-500 text-sm">
                Loading…
              </div>
            ) : (
              <RiskKnob
                value={riskPercent}
                onChange={handleRiskChange}
                isUpdating={updateSetting.isPending}
              />
            )}
          </CardContent>
        </Card>

        {/* Guard rails */}
        <Card className="border-[#2a2e39] bg-[#1e222d]/50">
          <CardHeader className="pb-2">
            <div className="flex items-center gap-2">
              <Shield className="h-4 w-4 text-emerald-500" />
              <CardTitle className="text-sm font-medium text-zinc-100">
                Guard rails
              </CardTitle>
            </div>
            <CardDescription className="text-[11px] text-zinc-500">
              Enable or disable safety guards. Changes apply immediately.
            </CardDescription>
          </CardHeader>
          <CardContent>
            {isLoading ? (
              <div className="flex h-32 items-center justify-center text-zinc-500 text-sm">
                Loading…
              </div>
            ) : (
              <GuardRailToggle
                items={guardRailItems}
                onToggle={handleGuardToggle}
                isUpdating={updateSetting.isPending}
              />
            )}
          </CardContent>
        </Card>
      </div>

      {/* Symbol overrides table */}
      <Card className="border-[#2a2e39] bg-[#1e222d]/50">
        <CardHeader className="pb-2">
          <div className="flex items-center gap-2">
            <Table2 className="h-4 w-4 text-emerald-500" />
            <CardTitle className="text-sm font-medium text-zinc-100">
              Symbol overrides
            </CardTitle>
          </div>
          <CardDescription className="text-[11px] text-zinc-500">
            Custom risk % and max lot size per pair (e.g. XAUUSD = 0.5%).
          </CardDescription>
        </CardHeader>
        <CardContent>
          <SymbolOverrideTable />
        </CardContent>
      </Card>
    </div>
  );
}
