'use client';

import {
  createContext,
  useContext,
  useEffect,
  useMemo,
  useRef,
  type ReactNode,
} from 'react';
import { useAlerts, type Alert } from '@/hooks/useAlerts';

interface AlertContextValue {
  alerts: Alert[];
  unreadCount: number;
  markAsRead: (id: number) => Promise<void> | void;
  clearAll: () => Promise<void> | void;
}

const AlertContext = createContext<AlertContextValue | undefined>(undefined);

export function useAlertContext(): AlertContextValue {
  const ctx = useContext(AlertContext);
  if (!ctx) {
    throw new Error('useAlertContext must be used within <AlertProvider>');
  }
  return ctx;
}

interface AlertProviderProps {
  children: ReactNode;
}

export function AlertProvider({ children }: AlertProviderProps) {
  const { alerts, unreadCount, markAsRead, clearAll } = useAlerts();
  const seenIdsRef = useRef<Set<number>>(new Set());

  // Fire a simple toast/notification when a new critical alert appears.
  useEffect(() => {
    if (!alerts.length) return;

    for (const alert of alerts) {
      const id = alert.id;
      if (seenIdsRef.current.has(id)) continue;

      seenIdsRef.current.add(id);

      const severity = String(alert.severity).toLowerCase();
      if (severity === 'critical' || severity === 'error') {
        const title = alert.title || alert.alert_type || 'Critical Alert';
        const body = alert.message;

        // Minimal fallback: browser alert; teams can wire in real toast system.
        if (typeof window !== 'undefined') {
          // eslint-disable-next-line no-alert
          window.alert(`${title}\n\n${body}`);
        } else {
          // eslint-disable-next-line no-console
          console.error('[Alert]', title, body);
        }
      }
    }
  }, [alerts]);

  const value = useMemo<AlertContextValue>(
    () => ({
      alerts,
      unreadCount,
      // Expose async signatures but underlying hooks already handle errors/logging.
      // eslint-disable-next-line @typescript-eslint/no-misused-promises
      markAsRead,
      // eslint-disable-next-line @typescript-eslint/no-misused-promises
      clearAll,
    }),
    [alerts, unreadCount, markAsRead, clearAll],
  );

  return <AlertContext.Provider value={value}>{children}</AlertContext.Provider>;
}

