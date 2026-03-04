'use client';

import { PnLText } from '@/components/ui/typography';

interface PnLDisplayProps {
  pnl: number | null;
  size?: 'sm' | 'md' | 'lg';
}

/**
 * Legacy PnL display wrapper.
 * Delegates to the design-system `PnLText` primitive so that
 * all profit/loss rendering shares the same semantics.
 */
export function PnLDisplay({ pnl, size = 'md' }: PnLDisplayProps) {
  const monoSize =
    size === 'sm' ? 'xs' : size === 'lg' ? 'lg' : 'base';

  return (
    <PnLText
      value={pnl}
      variant='raw'
      size={monoSize}
    />
  );
}
