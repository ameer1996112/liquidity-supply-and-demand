'use client';

import {
  createContext,
  useContext,
  useState,
  useCallback,
  type ReactNode,
} from 'react';

interface ShellActionsContextValue {
  copilotOpen: boolean;
  marketOpen: boolean;
  openCopilot: () => void;
  closeCopilot: () => void;
  toggleMarket: () => void;
  closeMarket: () => void;
}

const ShellActionsContext = createContext<ShellActionsContextValue | null>(
  null
);

export function ShellActionsProvider({ children }: { children: ReactNode }) {
  const [copilotOpen, setCopilotOpen] = useState(false);
  const [marketOpen, setMarketOpen] = useState(false);

  const openCopilot = useCallback(() => setCopilotOpen(true), []);
  const closeCopilot = useCallback(() => setCopilotOpen(false), []);
  const toggleMarket = useCallback(() => setMarketOpen((p) => !p), []);
  const closeMarket = useCallback(() => setMarketOpen(false), []);

  return (
    <ShellActionsContext.Provider
      value={{
        copilotOpen,
        marketOpen,
        openCopilot,
        closeCopilot,
        toggleMarket,
        closeMarket,
      }}
    >
      {children}
    </ShellActionsContext.Provider>
  );
}

export function useShellActions(): ShellActionsContextValue {
  const ctx = useContext(ShellActionsContext);
  if (!ctx) {
    throw new Error(
      'useShellActions must be used inside <ShellActionsProvider>'
    );
  }
  return ctx;
}
