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
    <div className='space-y-6'>
      {/* Header */}
      <div>
        <div className='flex items-center gap-2'>
          <Crosshair className='h-5 w-5 text-[#9db1d8]' />
          <h1 className='page-title text-xl font-semibold'>
            Position Command Center
          </h1>
        </div>
        <p className='page-subtitle mt-1 text-sm'>
          Manage active positions, exposure, and optimizer actions in real time.
        </p>
      </div>

      {/* Account Bar */}
      <div className='tv-card p-2'>
        <AccountBar />
      </div>

      {/* Portfolio Optimizer: batch actions, hedging, trailing stops */}
      <div className='tv-card p-2'>
        <OptimizerPanel />
      </div>

      {/* Positions */}
      {isLoading ? (
        <div className='grid grid-cols-1 gap-4 lg:grid-cols-2'>
          {[...Array(3)].map((_, i) => (
            <Skeleton
              key={i}
              className='h-48 rounded-xl bg-[rgba(30,45,72,0.72)]'
            />
          ))}
        </div>
      ) : positions.length > 0 ? (
        <div className='grid grid-cols-1 gap-4 lg:grid-cols-2'>
          {positions.map((pos) => (
            <PositionCard key={pos.id} position={pos} />
          ))}
        </div>
      ) : (
        <div className='tv-card flex flex-col items-center justify-center p-12'>
          <Crosshair className='mb-3 h-10 w-10 text-[#7488b2]' />
          <span className='text-sm text-[#a8b8da]'>No active positions</span>
          <span className='mt-1 text-xs text-[#8497be]'>
            Positions will appear here when trades are executed
          </span>
        </div>
      )}
    </div>
  );
}
