'use client';

import {
  createContext,
  useContext,
  useState,
  useCallback,
  useEffect,
  useRef,
} from 'react';
import { cn } from '@/lib/utils';
import {
  X,
  AlertTriangle,
  AlertCircle,
  Info,
  CheckCircle2,
  Zap,
} from 'lucide-react';

export interface Toast {
  id: string;
  title: string;
  message?: string;
  severity: 'critical' | 'warning' | 'info' | 'success' | 'signal';
  duration?: number;
  /** Optional correlation id to link to pipeline traces / audit logs. */
  correlationId?: string;
}

interface ToastContextValue {
  toasts: Toast[];
  addToast: (toast: Omit<Toast, 'id'>) => void;
  removeToast: (id: string) => void;
}

const ToastContext = createContext<ToastContextValue>({
  toasts: [],
  addToast: () => {},
  removeToast: () => {},
});

export const useToast = () => useContext(ToastContext);

const SEVERITY_STYLES: Record<
  Toast['severity'],
  {
    bg: string;
    border: string;
    leftBorder: string;
    text: string;
    bar: string;
    icon: React.ElementType;
  }
> = {
  critical: {
    bg: 'bg-[#0d1117]/95',
    border: 'border-[#f6465d]/20',
    leftBorder: '#f6465d',
    text: 'text-[#f6465d]',
    bar: 'bg-[#f6465d]',
    icon: AlertCircle,
  },
  warning: {
    bg: 'bg-[#0d1117]/95',
    border: 'border-[#f0b90b]/20',
    leftBorder: '#f0b90b',
    text: 'text-[#f0b90b]',
    bar: 'bg-[#f0b90b]',
    icon: AlertTriangle,
  },
  info: {
    bg: 'bg-[#0d1117]/95',
    border: 'border-[#3b82f6]/20',
    leftBorder: '#3b82f6',
    text: 'text-[#3b82f6]',
    bar: 'bg-[#3b82f6]',
    icon: Info,
  },
  success: {
    bg: 'bg-[#0d1117]/95',
    border: 'border-[#0ecb81]/20',
    leftBorder: '#0ecb81',
    text: 'text-[#0ecb81]',
    bar: 'bg-[#0ecb81]',
    icon: CheckCircle2,
  },
  signal: {
    bg: 'bg-[#0d1117]/95',
    border: 'border-[#8b5cf6]/20',
    leftBorder: '#8b5cf6',
    text: 'text-[#8b5cf6]',
    bar: 'bg-[#8b5cf6]',
    icon: Zap,
  },
};

function ToastItem({
  toast,
  onRemove,
}: {
  toast: Toast;
  onRemove: (id: string) => void;
}) {
  const style = SEVERITY_STYLES[toast.severity];
  const Icon = style.icon;
  const duration = toast.duration ?? 6000;
  const [progress, setProgress] = useState(100);
  const [visible, setVisible] = useState(false);

  // Mount animation
  useEffect(() => {
    const t = setTimeout(() => setVisible(true), 10);
    return () => clearTimeout(t);
  }, []);

  // Progress bar countdown
  useEffect(() => {
    if (duration === 0) return;
    const start = Date.now();
    const id = setInterval(() => {
      const elapsed = Date.now() - start;
      const pct = Math.max(0, 100 - (elapsed / duration) * 100);
      setProgress(pct);
      if (pct <= 0) clearInterval(id);
    }, 50);
    return () => clearInterval(id);
  }, [duration]);

  return (
    <div
      className={cn(
        'relative w-[340px] overflow-hidden rounded-xl border backdrop-blur-xl',
        'shadow-[0_8px_32px_rgba(0,0,0,0.6),0_2px_8px_rgba(0,0,0,0.4)]',
        'transition-all duration-300 ease-out',
        style.bg,
        style.border,
        visible ? 'translate-x-0 opacity-100' : 'translate-x-6 opacity-0'
      )}
      style={{ borderLeft: `3px solid ${style.leftBorder}` }}
    >
      <div className='flex items-start gap-3 px-4 py-3'>
        <Icon className={cn('h-4 w-4 mt-0.5 shrink-0', style.text)} />
        <div className='min-w-0 flex-1'>
          <p
            className={cn(
              'text-[13px] font-semibold leading-tight',
              style.text
            )}
            style={{ fontFamily: 'var(--font-sans)' }}
          >
            {toast.title}
          </p>
          {toast.message && (
            <p
              className='mt-0.5 text-[11px] text-[var(--to-text-secondary)] leading-relaxed'
              style={{ fontFamily: 'var(--font-sans)' }}
            >
              {toast.message}
            </p>
          )}
          {toast.correlationId && (
            <p className='mt-1 font-mono text-[9px] text-[var(--to-text-dim)]'>
              CID:{' '}
              <span className='text-[var(--to-text-secondary)]'>
                {toast.correlationId.slice(0, 12)}…
              </span>
            </p>
          )}
        </div>
        <button
          onClick={() => onRemove(toast.id)}
          className='mt-0.5 shrink-0 rounded p-0.5 text-[var(--to-text-dim)] hover:text-[var(--to-text-secondary)] transition-colors'
        >
          <X className='h-3.5 w-3.5' />
        </button>
      </div>

      {/* Progress bar */}
      {duration > 0 && (
        <div className='absolute bottom-0 left-0 right-0 h-[2px] bg-[var(--to-border)]'>
          <div
            className={cn('h-full transition-none', style.bar)}
            style={{ width: `${progress}%`, opacity: 0.5 }}
          />
        </div>
      )}
    </div>
  );
}

export function ToastProvider({ children }: { children: React.ReactNode }) {
  const [toasts, setToasts] = useState<Toast[]>([]);
  const timersRef = useRef<Map<string, ReturnType<typeof setTimeout>>>(
    new Map()
  );

  const removeToast = useCallback((id: string) => {
    setToasts((prev) => prev.filter((t) => t.id !== id));
    const timer = timersRef.current.get(id);
    if (timer) {
      clearTimeout(timer);
      timersRef.current.delete(id);
    }
  }, []);

  const addToast = useCallback(
    (toast: Omit<Toast, 'id'>) => {
      const id = `toast-${Date.now()}-${Math.random()
        .toString(36)
        .slice(2, 7)}`;
      const newToast: Toast = { ...toast, id };
      setToasts((prev) => [...prev.slice(-4), newToast]); // max 5

      const duration = toast.duration ?? 6000;
      if (duration > 0) {
        const timer = setTimeout(() => removeToast(id), duration);
        timersRef.current.set(id, timer);
      }
    },
    [removeToast]
  );

  useEffect(() => {
    return () => {
      timersRef.current.forEach((timer) => clearTimeout(timer));
    };
  }, []);

  return (
    <ToastContext.Provider value={{ toasts, addToast, removeToast }}>
      {children}
      {toasts.length > 0 && (
        <div
          className='fixed bottom-4 right-4 z-[9999] flex flex-col gap-2 pointer-events-none'
          aria-live='polite'
          aria-label='Notifications'
        >
          {toasts.map((t) => (
            <div key={t.id} className='pointer-events-auto'>
              <ToastItem toast={t} onRemove={removeToast} />
            </div>
          ))}
        </div>
      )}
    </ToastContext.Provider>
  );
}
