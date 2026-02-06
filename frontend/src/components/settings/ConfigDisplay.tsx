'use client';

import { cn } from '@/lib/utils';
import { Cog, Eye, EyeOff } from 'lucide-react';
import { useState } from 'react';

interface ConfigItem {
  key: string;
  value: string;
  sensitive?: boolean;
}

interface ConfigDisplayProps {
  title: string;
  items: ConfigItem[];
}

export function ConfigDisplay({ title, items }: ConfigDisplayProps) {
  const [showSensitive, setShowSensitive] = useState(false);

  return (
    <div className="tv-card">
      <div className="px-4 py-3 border-b border-[#2a2e39] flex items-center justify-between">
        <div className="flex items-center gap-2">
          <Cog className="w-4 h-4 text-zinc-500" />
          <span className="font-mono text-xs text-zinc-400 uppercase tracking-wider">
            {title}
          </span>
        </div>
        {items.some((i) => i.sensitive) && (
          <button
            onClick={() => setShowSensitive(!showSensitive)}
            className="flex items-center gap-1.5 text-[10px] text-zinc-500 hover:text-zinc-300 transition-colors font-mono"
          >
            {showSensitive ? <EyeOff className="w-3 h-3" /> : <Eye className="w-3 h-3" />}
            {showSensitive ? 'Hide' : 'Show'}
          </button>
        )}
      </div>
      <div className="divide-y divide-[#2a2e39]">
        {items.map((item) => (
          <div key={item.key} className="px-4 py-2.5 flex items-center justify-between">
            <span className="text-[11px] text-zinc-500 uppercase tracking-wider font-mono">
              {item.key}
            </span>
            <span className={cn('font-mono text-xs', item.value ? 'text-zinc-300' : 'text-zinc-600')}>
              {item.sensitive && !showSensitive
                ? item.value
                  ? `${item.value.slice(0, 8)}${'*'.repeat(Math.max(0, item.value.length - 8))}`
                  : 'Not set'
                : item.value || 'Not set'}
            </span>
          </div>
        ))}
      </div>
    </div>
  );
}
