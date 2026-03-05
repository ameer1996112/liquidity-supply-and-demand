'use client';

import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { ReactQueryDevtools } from '@tanstack/react-query-devtools';
import { useState } from 'react';

export function QueryProvider({ children }: { children: React.ReactNode }) {
  const [queryClient] = useState(
    () =>
      new QueryClient({
        defaultOptions: {
          queries: {
            staleTime: 1000 * 60, // 1 minute — data considered fresh
            gcTime: 1000 * 60 * 5, // 5 minutes — keep unused cache
            refetchOnWindowFocus: false, // don't hammer API on tab switch
            refetchOnReconnect: true, // do refresh when network comes back
            retry: 2, // 2 retries (not 3)
            retryDelay: (attempt) => Math.min(1000 * 2 ** attempt, 30_000), // exponential: 1s, 2s, 4s…30s max
          },
          mutations: {
            retry: 0, // mutations should not auto-retry
          },
        },
      })
  );

  return (
    <QueryClientProvider client={queryClient}>
      {children}
      <ReactQueryDevtools initialIsOpen={false} />
    </QueryClientProvider>
  );
}
