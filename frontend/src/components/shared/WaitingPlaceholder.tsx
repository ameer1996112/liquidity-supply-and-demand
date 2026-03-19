'use client';

interface WaitingPlaceholderProps {
  message?: string;
  className?: string;
}

/**
 * Empty-state placeholder shown inside chart/log areas when there is no data yet.
 * Uses a subtle pulse animation to signal the system is live and waiting.
 */
export function WaitingPlaceholder({
  message = 'Waiting for First Trade...',
  className = '',
}: WaitingPlaceholderProps) {
  return (
    <div
      className={`flex flex-col items-center justify-center gap-3 h-full w-full min-h-[120px] ${className}`}
    >
      {/* Animated dot */}
      <span className='relative flex h-3 w-3'>
        <span className='animate-ping absolute inline-flex h-full w-full rounded-full bg-[#26a69a] opacity-40' />
        <span className='relative inline-flex rounded-full h-3 w-3 bg-[#26a69a]/60' />
      </span>

      {/* Label */}
      <span className='font-mono text-[11px] text-[var(--to-text-dim)] animate-pulse tracking-wider'>
        {message}
      </span>
    </div>
  );
}
