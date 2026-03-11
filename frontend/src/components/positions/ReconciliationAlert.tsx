'use client';

import { AlertCircle, CheckCircle, RefreshCw } from 'lucide-react';
import { ReconciliationInfo } from '@/hooks/usePositions';
import { cn } from '@/lib/utils';

interface ReconciliationAlertProps {
  reconciliation: ReconciliationInfo;
  onSync?: () => void;
}

export function ReconciliationAlert({
  reconciliation,
  onSync,
}: ReconciliationAlertProps) {
  const {
    db_position_count,
    broker_position_count,
    matched_count,
    stale_in_db,
    missing_in_db,
    has_mismatches,
  } = reconciliation;

  if (!has_mismatches) {
    return (
      <div className='tv-card'>
        <div className='flex items-center gap-3 px-4 py-3'>
          <CheckCircle className='h-4 w-4 text-green-500' />
          <div className='flex-1'>
            <p className='text-sm font-medium text-zinc-200'>
              Positions synchronized
            </p>
            <p className='text-xs text-zinc-500'>
              {matched_count} {matched_count === 1 ? 'position' : 'positions'}{' '}
              matched with broker
            </p>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className='tv-card border-l-4 border-yellow-500'>
      <div className='flex items-start gap-3 px-4 py-3'>
        <AlertCircle className='h-5 w-5 text-yellow-500 mt-0.5' />
        <div className='flex-1'>
          <p className='text-sm font-semibold text-zinc-200'>
            Position reconciliation warning
          </p>
          <div className='mt-1 space-y-1 text-xs text-zinc-400'>
            <div className='flex items-center gap-4'>
              <span>Database: {db_position_count} positions</span>
              <span>Broker: {broker_position_count} positions</span>
              <span className='text-green-400'>
                Matched: {matched_count}
              </span>
            </div>
            {stale_in_db > 0 && (
              <p className='text-yellow-400'>
                ⚠️ {stale_in_db} stale{' '}
                {stale_in_db === 1 ? 'position' : 'positions'} in database
                (closed on broker but not in DB)
              </p>
            )}
            {missing_in_db > 0 && (
              <p className='text-yellow-400'>
                ⚠️ {missing_in_db}{' '}
                {missing_in_db === 1 ? 'position' : 'positions'} on broker not
                tracked in database
              </p>
            )}
          </div>
          {onSync && (
            <button
              onClick={onSync}
              className={cn(
                'mt-3 flex items-center gap-2 px-3 py-1.5',
                'bg-yellow-500/10 hover:bg-yellow-500/20',
                'border border-yellow-500/20 hover:border-yellow-500/30',
                'rounded text-xs font-medium text-yellow-400',
                'transition-colors',
              )}
            >
              <RefreshCw className='h-3 w-3' />
              Sync & cleanup stale positions
            </button>
          )}
        </div>
      </div>
    </div>
  );
}
