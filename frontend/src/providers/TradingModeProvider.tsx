'use client';

import {
  createContext,
  useContext,
  useState,
  useCallback,
  type ReactNode,
} from 'react';
import type { TradingMode } from '@/types/trading';

interface TradingModeContextValue {
  mode: TradingMode;
  setMode: (mode: TradingMode) => void;
}

const TradingModeContext = createContext<TradingModeContextValue>({
  mode: 'LIVE',
  setMode: () => {},
});

const STORAGE_KEY = 'trading-mode';

export function TradingModeProvider({ children }: { children: ReactNode }) {
  const [mode, setModeState] = useState<TradingMode>(() => {
    if (typeof window === 'undefined') return 'LIVE';
    const stored = localStorage.getItem(STORAGE_KEY);
    return stored === 'PAPER' ? 'PAPER' : 'LIVE';
  });

  const setMode = useCallback((m: TradingMode) => {
    setModeState(m);
    localStorage.setItem(STORAGE_KEY, m);
  }, []);

  return (
    <TradingModeContext.Provider value={{ mode, setMode }}>
      {children}
    </TradingModeContext.Provider>
  );
}

export function useTradingMode() {
  return useContext(TradingModeContext);
}
