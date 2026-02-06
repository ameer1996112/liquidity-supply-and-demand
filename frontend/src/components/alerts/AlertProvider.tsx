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
import { useToast } from '@/components/ui/toast';

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
  const { addToast } = useToast();
  const seenIdsRef = useRef<Set<number>>(new Set());

  // Show toast for new alerts via the custom toast system.
  useEffect(() => {
    if (!alerts.length) return;

    for (const alert of alerts) {
      const id = alert.id;
      if (seenIdsRef.current.has(id)) continue;

      seenIdsRef.current.add(id);

      const severity = String(alert.severity).toLowerCase();
      const title = alert.title || alert.alert_type || 'Alert';
      const toastSeverity =
        severity === 'critical' || severity === 'error'
          ? 'critical'
          : severity === 'warning'
            ? 'warning'
            : 'info';

      addToast({
        title,
        message: alert.message,
        severity: toastSeverity,
        duration: toastSeverity === 'critical' ? 15_000 : 8_000,
      });
    }
  }, [alerts, addToast]);

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

