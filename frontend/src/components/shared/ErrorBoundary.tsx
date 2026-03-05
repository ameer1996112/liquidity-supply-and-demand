'use client';

import React from 'react';
import { AlertTriangle, RefreshCw } from 'lucide-react';

interface ErrorBoundaryState {
  hasError: boolean;
  error: Error | null;
}

interface ErrorBoundaryProps {
  children: React.ReactNode;
  /** Custom fallback UI */
  fallback?: React.ReactNode;
  /** Label shown in the default fallback (e.g. "Analytics", "Risk Monitor") */
  label?: string;
  /** Called when the user clicks "Try again" */
  onReset?: () => void;
}

/**
 * Route-level error boundary.
 * Catches render errors and shows a graceful fallback with a retry button.
 * Wrap each page or heavy panel with this to prevent full-app crashes.
 */
export class ErrorBoundary extends React.Component<
  ErrorBoundaryProps,
  ErrorBoundaryState
> {
  constructor(props: ErrorBoundaryProps) {
    super(props);
    this.state = { hasError: false, error: null };
  }

  static getDerivedStateFromError(error: Error): ErrorBoundaryState {
    return { hasError: true, error };
  }

  componentDidCatch(error: Error, info: React.ErrorInfo) {
    // Log to console in dev; swap for Sentry/Datadog in production
    if (process.env.NODE_ENV === 'development') {
      console.error('[ErrorBoundary]', error, info.componentStack);
    }
  }

  handleReset = () => {
    this.setState({ hasError: false, error: null });
    this.props.onReset?.();
  };

  render() {
    if (!this.state.hasError) {
      return this.props.children;
    }

    if (this.props.fallback) {
      return this.props.fallback;
    }

    const { label = 'this section' } = this.props;
    const { error } = this.state;

    return (
      <div className='flex min-h-[200px] flex-col items-center justify-center gap-4 rounded-xl border border-[var(--to-border)] bg-[var(--to-surface)] p-8 text-center'>
        <div className='flex h-12 w-12 items-center justify-center rounded-full bg-[var(--to-short)]/10 ring-1 ring-[var(--to-short)]/20'>
          <AlertTriangle className='h-6 w-6 text-[var(--to-short)]' />
        </div>

        <div className='space-y-1'>
          <p className='text-sm font-semibold text-[var(--to-text-primary)]'>
            Something went wrong in {label}
          </p>
          {process.env.NODE_ENV === 'development' && error?.message && (
            <p className='max-w-sm font-mono text-[11px] text-[var(--to-text-dim)]'>
              {error.message}
            </p>
          )}
        </div>

        <button
          onClick={this.handleReset}
          className='flex items-center gap-2 rounded-lg border border-[var(--to-border)] bg-[var(--to-surface-raised)] px-4 py-2 text-xs font-medium text-[var(--to-text-secondary)] transition-colors hover:border-[var(--to-accent-blue)]/40 hover:text-[var(--to-text-primary)]'
        >
          <RefreshCw className='h-3.5 w-3.5' />
          Try again
        </button>
      </div>
    );
  }
}

/**
 * Functional wrapper for convenience — wraps children in an ErrorBoundary.
 */
export function WithErrorBoundary({
  children,
  label,
  fallback,
}: {
  children: React.ReactNode;
  label?: string;
  fallback?: React.ReactNode;
}) {
  return (
    <ErrorBoundary label={label} fallback={fallback}>
      {children}
    </ErrorBoundary>
  );
}
