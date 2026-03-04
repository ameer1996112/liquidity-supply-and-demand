'use client';

import { Search } from 'lucide-react';
import { SymbolScanner } from '@/components/scanner/SymbolScanner';
import { PatternAnalysis } from '@/components/journal/PatternAnalysis';
import { useQuery } from '@tanstack/react-query';
import { fetchSignals } from '@/lib/supabase';
import { TradingSignal } from '@/types/trading';

export default function ScannerPage() {
  const { data: signals = [] } = useQuery({
    queryKey: ['scanner-page-signals'],
    queryFn: () => fetchSignals({ limit: 500 }),
    staleTime: 5 * 60_000,
  });

  return (
    <div className='space-y-4'>
      {/* Header */}
      <div>
        <div className='flex items-center gap-2'>
          <Search className='h-4 w-4 text-[#a78bfa]' />
          <h1 className='page-title text-lg font-semibold'>Symbol Scanner</h1>
        </div>
        <p className='page-subtitle mt-0.5 text-xs'>
          Scan, filter, and analyze signals by mode, symbol, date, and score.
        </p>
      </div>

      {/* Main Scanner */}
      <SymbolScanner />

      {/* Pattern Analysis */}
      {signals.length >= 3 && (
        <PatternAnalysis signals={signals as TradingSignal[]} />
      )}
    </div>
  );
}
