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
import { X, AlertTriangle, AlertCircle, Info, CheckCircle2 } from 'lucide-react';

export interface Toast {
  id: string;
  title: string;
  message?: string;
  severity: 'critical' | 'warning' | 'info' | 'success';
  duration?: number;
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
  { bg: string; border: string; text: string; icon: React.ElementType }
> = {
  critical: {
    bg: 'bg-[#ef5350]/10',
    border: 'border-[#ef5350]/30',
    text: 'text-[#ef5350]',
    icon: AlertCircle,
  },
  warning: {
    bg: 'bg-amber-500/10',
    border: 'border-amber-500/30',
    text: 'text-amber-400',
    icon: AlertTriangle,
  },
  info: {
    bg: 'bg-blue-500/10',
    border: 'border-blue-500/30',
    text: 'text-blue-400',
    icon: Info,
  },
  success: {
    bg: 'bg-[#26a69a]/10',
    border: 'border-[#26a69a]/30',
    text: 'text-[#26a69a]',
    icon: CheckCircle2,
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

  return (
    <div
      className={cn(
        'flex items-start gap-3 px-4 py-3 rounded-lg border backdrop-blur-sm',
        'animate-in slide-in-from-right-5 fade-in duration-300',
        style.bg,
        style.border,
      )}
    >
      <Icon className={cn('w-4 h-4 mt-0.5 shrink-0', style.text)} />
      <div className="flex-1 min-w-0">
        <p className={cn('font-mono text-xs font-semibold', style.text)}>
          {toast.title}
        </p>
        {toast.message && (
          <p className="font-mono text-[10px] text-zinc-400 mt-0.5 line-clamp-2">
            {toast.message}
          </p>
        )}
      </div>
      <button
        onClick={() => onRemove(toast.id)}
        className="text-zinc-500 hover:text-zinc-300 transition-colors shrink-0"
      >
        <X className="w-3.5 h-3.5" />
      </button>
    </div>
  );
}

export function ToastProvider({ children }: { children: React.ReactNode }) {
  const [toasts, setToasts] = useState<Toast[]>([]);
  const timersRef = useRef<Map<string, ReturnType<typeof setTimeout>>>(new Map());

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
      const id = `toast-${Date.now()}-${Math.random().toString(36).slice(2, 7)}`;
      const newToast: Toast = { ...toast, id };

      setToasts((prev) => [...prev.slice(-4), newToast]); // Keep max 5

      const duration = toast.duration ?? 8000;
      const timer = setTimeout(() => removeToast(id), duration);
      timersRef.current.set(id, timer);
    },
    [removeToast],
  );

  useEffect(() => {
    return () => {
      timersRef.current.forEach((timer) => clearTimeout(timer));
    };
  }, []);

  return (
    <ToastContext.Provider value={{ toasts, addToast, removeToast }}>
      {children}
      {/* Toast container */}
      {toasts.length > 0 && (
        <div className="fixed bottom-4 right-4 z-50 flex flex-col gap-2 max-w-sm">
          {toasts.map((toast) => (
            <ToastItem key={toast.id} toast={toast} onRemove={removeToast} />
          ))}
        </div>
      )}
    </ToastContext.Provider>
  );
}
