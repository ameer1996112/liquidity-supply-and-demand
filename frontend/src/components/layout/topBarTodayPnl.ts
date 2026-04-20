import type { DashboardSummary } from '@/types/trading';

type AccountPnlSource = {
  account_name: string;
  daily_pnl?: number | null;
  realized_pnl_today?: number | null;
};

type ResolveTopBarTodayPnlArgs = {
  selectedAccountName: string | null;
  summary?: DashboardSummary;
  activeTradingAccounts: AccountPnlSource[];
  todayPnlFromStats?: number | null;
  riskDailyPnl?: number | null;
};

function getAccountSnapshotPnl(account: AccountPnlSource | undefined): number | null {
  if (!account) return null;
  return account.daily_pnl ?? account.realized_pnl_today ?? null;
}

export function resolveTopBarTodayPnl({
  selectedAccountName,
  summary,
  activeTradingAccounts,
  todayPnlFromStats,
  riskDailyPnl,
}: ResolveTopBarTodayPnlArgs): number | null {
  const accountsTodayPnl =
    activeTradingAccounts.length > 0
      ? activeTradingAccounts.reduce(
          (sum, account) => sum + (account.daily_pnl ?? account.realized_pnl_today ?? 0),
          0
        )
      : null;

  if (selectedAccountName) {
    const summaryAccount = summary?.accounts.find(
      (account) => account.name === selectedAccountName
    );
    if (summaryAccount) return summaryAccount.pnl_today;

    const selectedAccount = activeTradingAccounts.find(
      (account) => account.account_name === selectedAccountName
    );
    const selectedAccountPnl = getAccountSnapshotPnl(selectedAccount);
    if (selectedAccountPnl != null) return selectedAccountPnl;

    if (todayPnlFromStats != null) return todayPnlFromStats;
    return riskDailyPnl ?? null;
  }

  if (summary) return summary.total_pnl_today;
  if (activeTradingAccounts.length > 1) return accountsTodayPnl;
  if (todayPnlFromStats != null) return todayPnlFromStats;
  if (accountsTodayPnl != null) return accountsTodayPnl;
  return riskDailyPnl ?? null;
}
