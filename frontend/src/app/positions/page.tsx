'use client';

import { useActivePositions } from '@/hooks/usePositions';
import { AccountBar } from '@/components/positions/AccountBar';
import { PositionCard } from '@/components/positions/PositionCard';
import { OptimizerPanel } from '@/components/portfolio/OptimizerPanel';
import { Crosshair } from 'lucide-react';
import { Skeleton } from '@/components/ui/skeleton';

export default function PositionsPage() {
  const { data, isLoading } = useActivePositions();
  const positions = data?.positions || [];

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
        <div className='grid grid-cols-1 gap-3 lg:grid-cols-2'>
          {[...Array(3)].map((_, i) => (
            <Skeleton key={i} className='h-44 rounded-lg bg-slate-800/60' />
          ))}
        </div>
      ) : positions.length > 0 ? (
        <div className='grid grid-cols-1 gap-3 lg:grid-cols-2'>
          {positions.map((pos) => (
            <PositionCard key={pos.id} position={pos} />
          ))}
        </div>
      ) : (
        <div className='tv-card'>
          <div className='empty-state py-14'>
            <span className='empty-state-text'>[ NO ACTIVE POSITIONS ]</span>
            <span
              className='mt-1 text-[10px] text-slate-700'
              style={{ fontFamily: 'var(--font-mono)' }}
            >
              positions appear here when 5m zones are triggered
            </span>
          </div>
        </div>
      )}
    </div>
  );
}
