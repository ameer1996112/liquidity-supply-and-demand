'use client';

import { Suspense, useMemo } from 'react';
import { useSearchParams } from 'next/navigation';
import { useActivePositions } from '@/hooks/usePositions';
import { AccountBar } from '@/components/positions/AccountBar';
import { PositionCard } from '@/components/positions/PositionCard';
import { OptimizerPanel } from '@/components/portfolio/OptimizerPanel';
import { Crosshair } from 'lucide-react';
import { PanelEmptyState } from '@/components/shared/PanelEmptyState';
import { TableSkeleton } from '@/components/shared/TableStates';

function PositionsPageContent() {
  const { data, isLoading } = useActivePositions();
  const searchParams = useSearchParams();
  const highlightTicket = searchParams.get('order_id');
  const rawPositions = data?.positions || [];

  const positions = useMemo(() => {
    if (!highlightTicket) return rawPositions;
    return [...rawPositions].sort((a, b) => {
      const aMatch = a.broker_order_id === highlightTicket;
      const bMatch = b.broker_order_id === highlightTicket;
      if (aMatch === bMatch) return 0;
      return aMatch ? -1 : 1;
    });
  }, [rawPositions, highlightTicket]);

  return (
    <div className='space-y-4'>
      {/* Header */}
      <div>
        <div className='flex items-center gap-2'>
          <Crosshair className='h-4 w-4 text-slate-400' />
          <h1 className='page-title text-lg font-semibold'>
            Position Command Center
          </h1>
        </div>
        <p className='page-subtitle mt-0.5 text-xs'>
          Manage active positions, exposure, and optimizer actions in real time.
        </p>
      </div>

      {/* Account Bar */}
      <div className='tv-card p-2'>
        <AccountBar />
      </div>

      {/* Portfolio Optimizer */}
      <div className='tv-card p-2'>
        <OptimizerPanel />
      </div>

      {/* Positions grid */}
      {isLoading ? (
        <div className='tv-card p-3'>
          <TableSkeleton rowCount={4} columnCount={4} />
        </div>
      ) : positions.length > 0 ? (
        <div className='grid grid-cols-1 gap-3 lg:grid-cols-2'>
          {positions.map((pos) => (
            <PositionCard key={pos.id} position={pos} />
          ))}
        </div>
      ) : (
        <div className='tv-card p-4'>
          <PanelEmptyState
            title='No active positions'
            description='Positions appear here when 5m zones are triggered.'
          />
        </div>
      )}
    </div>
  );
}

export default function PositionsPage() {
  return (
    <Suspense
      fallback={
        <div className='p-4 text-xs text-slate-500'>
          Loading positions dashboard...
        </div>
      }
    >
      <PositionsPageContent />
    </Suspense>
  );
}
