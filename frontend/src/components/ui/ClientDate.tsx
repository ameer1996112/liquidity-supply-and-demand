'use client';

import { useIsMounted } from '@/hooks/useIsMounted';

interface ClientDateProps {
  /** A function called only on the client to produce the date string. */
  render: () => string;
  /** Placeholder shown during SSR (server render). Default: empty string. */
  placeholder?: string;
  className?: string;
}

/**
 * Renders a dynamic date string ONLY on the client, preventing React Hydration Error #418.
 *
 * Usage:
 * ```tsx
 * <ClientDate render={() => new Date(signal.created_at).toLocaleString()} />
 * <ClientDate render={() => formatDistanceToNow(new Date(ts), { addSuffix: true })} />
 * ```
 */
export function ClientDate({
  render,
  placeholder = '',
  className,
}: ClientDateProps) {
  const mounted = useIsMounted();
  return <span className={className}>{mounted ? render() : placeholder}</span>;
}
