'use client';

import { useMemo, useState } from 'react';

interface UseVirtualizedListOptions<T> {
  items: T[];
  itemHeight: number;
  containerHeight: number;
  overscan?: number;
}

export function useVirtualizedList<T>({
  items,
  itemHeight,
  containerHeight,
  overscan = 6,
}: UseVirtualizedListOptions<T>) {
  const [scrollTop, setScrollTop] = useState(0);

  const totalHeight = items.length * itemHeight;

  const startIndex = Math.max(0, Math.floor(scrollTop / itemHeight) - overscan);
  const endIndex = Math.min(
    items.length,
    Math.ceil((scrollTop + containerHeight) / itemHeight) + overscan
  );

  const visibleItems = useMemo(
    () => items.slice(startIndex, endIndex),
    [items, startIndex, endIndex]
  );

  const offsetY = startIndex * itemHeight;

  return {
    scrollTop,
    setScrollTop,
    visibleItems,
    totalHeight,
    offsetY,
    startIndex,
    endIndex,
  };
}
