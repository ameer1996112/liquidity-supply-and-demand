type AccountLike = {
  account_name?: string | null;
  status?: string | null;
  is_active?: boolean | null;
  is_archived?: boolean | null;
  selected_for_trading?: boolean | null;
  pause_trading?: boolean | null;
};

type SignalLike = {
  account_name?: string | null;
};

function normalizeAccountName(name: string | null | undefined): string {
  return typeof name === 'string' ? name.trim() : '';
}

export function isTradingEnabledAccount(account: AccountLike): boolean {
  const name = normalizeAccountName(account.account_name);
  if (!name) return false;
  if (account.is_archived || account.status?.toLowerCase() === 'archived') return false;
  if (account.is_active === false) return false;
  if (account.pause_trading === true) return false;
  if (account.selected_for_trading === false) return false;
  return true;
}

export function buildEnabledAccountNames(accounts: AccountLike[]): string[] {
  const namesByKey = new Map<string, string>();

  for (const account of accounts) {
    if (!isTradingEnabledAccount(account)) continue;
    const name = normalizeAccountName(account.account_name);
    namesByKey.set(name.toLowerCase(), name);
  }

  return Array.from(namesByKey.values()).sort((left, right) => left.localeCompare(right));
}

export function filterSignalsByEnabledAccounts<TSignal extends SignalLike>(
  signals: TSignal[],
  enabledAccountNames: string[],
): TSignal[] {
  const enabledKeys = new Set(
    enabledAccountNames.map((name) => name.trim().toLowerCase()).filter(Boolean),
  );

  if (enabledKeys.size === 0) return [];

  return signals.filter((signal) => {
    const accountName = normalizeAccountName(signal.account_name);
    return accountName ? enabledKeys.has(accountName.toLowerCase()) : false;
  });
}

export function countSignalsByAccount(signals: SignalLike[]): Record<string, number> {
  const counts: Record<string, number> = {};

  for (const signal of signals) {
    const name = normalizeAccountName(signal.account_name);
    if (name) counts[name] = (counts[name] ?? 0) + 1;
  }

  return counts;
}
