'use client';

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useRef,
  useState,
} from 'react';
import { cn } from '@/lib/utils';
import {
  CheckCircle2,
  AlertTriangle,
  XCircle,
  Info,
  X,
  Zap,
} from 'lucide-react';

// ── Types ─────────────────────────────────────────────────────────────────────

export type ToastVariant = 'success' | 'error' | 'warning' | 'info' | 'signal';

export interface Toast {
  id: string;
  title: string;
  description?: string;
  variant?: ToastVariant;
  duration?: number; // ms, 0 = persistent
}

interface ToastContextValue {
  toasts: Toast[];
  toast: (opts: Omit<Toast, 'id'>) => string;
  dismiss: (id: string) => void;
  dismissAll: () => void;
}

// ── Context ───────────────────────────────────────────────────────────────────

const ToastContext = createContext<ToastContextValue | null>(null);

// ── Hook ──────────────────────────────────────────────────────────────────────

export function useToast() {
  const ctx = useContext(ToastContext);
  if (!ctx) throw new Error('useToast must be used within ToastProvider');
  return ctx;
}

// ── Toast Item ────────────────────────────────────────────────────────────────

const VARIANT_CONFIG: Record<
  ToastVariant,
  {
    icon: React.ReactNode;
    border: string;
    bg: string;
    titleColor: string;
    barColor: string;
  }
> = {
  success: {
    icon: <CheckCircle2 className='h-4 w-4 text-[#0ecb81]' />,
    border: 'border-[#0ecb81]/25',
    bg: 'bg-[#0ecb81]/8',
    titleColor: 'text-[#0ecb81]',
    barColor: 'bg-[#0ecb81]',
  },
  error: {
    icon: <XCircle className='h-4 w-4 text-[#f6465d]' />,
    border: 'border-[#f6465d]/25',
    bg: 'bg-[#f6465d]/8',
    titleColor: 'text-[#f6465d]',
    barColor: 'bg-[#f6465d]',
  },
  warning: {
    icon: <AlertTriangle className='h-4 w-4 text-[#f0b90b]' />,
    border: 'border-[#f0b90b]/25',
    bg: 'bg-[#f0b90b]/8',
    titleColor: 'text-[#f0b90b]',
    barColor: 'bg-[#f0b90b]',
  },
  info: {
    icon: <Info className='h-4 w-4 text-[#3b82f6]' />,
    border: 'border-[#3b82f6]/25',
    bg: 'bg-[#3b82f6]/8',
    titleColor: 'text-[#3b82f6]',
    barColor: 'bg-[#3b82f6]',
  },
  signal: {
    icon: <Zap className='h-4 w-4 text-[#8b5cf6]' />,
    border: 'border-[#8b5cf6]/25',
    bg: 'bg-[#8b5cf6]/8',
    titleColor: 'text-[#8b5cf6]',
    barColor: 'bg-[#8b5cf6]',
  },
};

function ToastItem({
  toast,
  onDismiss,
}: {
  toast: Toast;
  onDismiss: (id: string) => void;
}) {
  const [visible, setVisible] = useState(false);
  const [leaving, setLeaving] = useState(false);
  const [progress, setProgress] = useState(100);
  const duration = toast.duration ?? 4500;
  const cfg = VARIANT_CONFIG[toast.variant ?? 'info'];

  // Mount animation
  useEffect(() => {
    const t = setTimeout(() => setVisible(true), 10);
    return () => clearTimeout(t);
  }, []);

  // Auto-dismiss with progress bar
  useEffect(() => {
    if (duration === 0) return;
    const start = Date.now();
    const interval = setInterval(() => {
      const elapsed = Date.now() - start;
      const pct = Math.max(0, 100 - (elapsed / duration) * 100);
      setProgress(pct);
      if (pct <= 0) {
        clearInterval(interval);
        handleDismiss();
      }
    }, 50);
    return () => clearInterval(interval);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [duration]);

  const handleDismiss = useCallback(() => {
    setLeaving(true);
    setTimeout(() => onDismiss(toast.id), 300);
  }, [onDismiss, toast.id]);

  return (
    <div
      className={cn(
        'relative w-[340px] overflow-hidden rounded-xl border backdrop-blur-xl',
        'shadow-[0_8px_32px_rgba(0,0,0,0.5)]',
        'transition-all duration-300 ease-out',
        cfg.border,
        cfg.bg,
        visible && !leaving
          ? 'translate-x-0 opacity-100'
          : 'translate-x-8 opacity-0'
      )}
      style={{
        background: 'rgba(13,17,23,0.92)',
        borderLeft: `3px solid`,
        borderLeftColor:
          toast.variant === 'success'
            ? '#0ecb81'
            : toast.variant === 'error'
            ? '#f6465d'
            : toast.variant === 'warning'
            ? '#f0b90b'
            : toast.variant === 'signal'
            ? '#8b5cf6'
            : '#3b82f6',
      }}
    >
      <div className='flex items-start gap-3 px-4 py-3'>
        <div className='mt-0.5 shrink-0'>{cfg.icon}</div>
        <div className='min-w-0 flex-1'>
          <p
            className={cn(
              'text-[13px] font-semibold leading-tight',
              cfg.titleColor
            )}
            style={{ fontFamily: 'var(--font-sans)' }}
          >
            {toast.title}
          </p>
          {toast.description && (
            <p
              className='mt-0.5 text-[11px] text-[var(--to-text-secondary)] leading-relaxed'
              style={{ fontFamily: 'var(--font-sans)' }}
            >
              {toast.description}
            </p>
          )}
        </div>
        <button
          onClick={handleDismiss}
          className='mt-0.5 shrink-0 rounded p-0.5 text-[var(--to-text-dim)] hover:text-[var(--to-text-secondary)] transition-colors'
        >
          <X className='h-3.5 w-3.5' />
        </button>
      </div>

      {/* Progress bar */}
      {duration > 0 && (
        <div className='absolute bottom-0 left-0 right-0 h-[2px] bg-[var(--to-border)]'>
          <div
            className={cn('h-full transition-none', cfg.barColor)}
            style={{ width: `${progress}%`, opacity: 0.6 }}
          />
        </div>
      )}
    </div>
  );
}

// ── Provider ──────────────────────────────────────────────────────────────────

export function ToastProvider({ children }: { children: React.ReactNode }) {
  const [toasts, setToasts] = useState<Toast[]>([]);
  const counterRef = useRef(0);

  const toast = useCallback((opts: Omit<Toast, 'id'>): string => {
    const id = `toast-${++counterRef.current}`;
    setToasts((prev) => [...prev.slice(-4), { ...opts, id }]); // max 5 toasts
    return id;
  }, []);

  const dismiss = useCallback((id: string) => {
    setToasts((prev) => prev.filter((t) => t.id !== id));
  }, []);

  const dismissAll = useCallback(() => {
    setToasts([]);
  }, []);

  return (
    <ToastContext.Provider value={{ toasts, toast, dismiss, dismissAll }}>
      {children}

      {/* Toast container — fixed bottom-right */}
      <div
        className='fixed bottom-4 right-4 z-[9999] flex flex-col gap-2 pointer-events-none'
        aria-live='polite'
        aria-label='Notifications'
      >
        {toasts.map((t) => (
          <div key={t.id} className='pointer-events-auto'>
            <ToastItem toast={t} onDismiss={dismiss} />
          </div>
        ))}
      </div>
    </ToastContext.Provider>
  );
}
