'use client';

import { useActivePositions } from '@/hooks/usePositions';
import { AccountBar } from '@/components/positions/AccountBar';
import { PositionCard } from '@/components/positions/PositionCard';
import { Crosshair } from 'lucide-react';
import { Skeleton } from '@/components/ui/skeleton';

export default function PositionsPage() {
  const { data, isLoading } = useActivePositions();
  const positions = data?.positions || [];

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center gap-2">
        <Crosshair className="w-5 h-5 text-zinc-400" />
        <h1 className="text-lg font-semibold text-zinc-100">
          Position Command Center
        </h1>
      </div>

      {/* Account Bar */}
      <AccountBar />

      {/* Positions */}
      {isLoading ? (
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
          {[...Array(3)].map((_, i) => (
            <Skeleton key={i} className="h-48 rounded-lg bg-[#1e222d]" />
          ))}
        </div>
      ) : positions.length > 0 ? (
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
          {positions.map((pos) => (
            <PositionCard key={pos.id} position={pos} />
          ))}
        </div>
      ) : (
        <div className="tv-card p-12 flex flex-col items-center justify-center">
          <Crosshair className="w-10 h-10 text-zinc-700 mb-3" />
          <span className="text-sm text-zinc-500">No active positions</span>
          <span className="text-xs text-zinc-600 mt-1">
            Positions will appear here when trades are executed
          </span>
        </div>
      )}
    </div>
  );
}
