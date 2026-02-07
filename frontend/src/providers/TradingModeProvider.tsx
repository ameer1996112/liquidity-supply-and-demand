'use client';

import {
  createContext,
  useContext,
  useState,
  useEffect,
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
  const [mode, setModeState] = useState<TradingMode>('LIVE');

  useEffect(() => {
    const stored = localStorage.getItem(STORAGE_KEY);
    if (stored === 'LIVE' || stored === 'PAPER') setModeState(stored);
  }, []);

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
