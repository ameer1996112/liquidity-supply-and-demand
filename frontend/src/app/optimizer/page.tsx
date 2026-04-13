'use client';

import { OptimizerRunsWorkspace } from '@/components/optimizer/OptimizerRunsWorkspace';

export default function OptimizerPage() {
  return (
    <div className='space-y-4 animate-fade-in-up'>
      <div className='flex items-start justify-between gap-3'>
        <div>
          <h1 className='page-title text-lg font-semibold'>Optimizer</h1>
          <p className='page-subtitle mt-0.5 text-xs'>
            Launch parallel optimizer runs, track live progress, and inspect run history.
          </p>
        </div>
        <span className='tf-badge'>OPS</span>
      </div>
      <OptimizerRunsWorkspace />
    </div>
  );
}
