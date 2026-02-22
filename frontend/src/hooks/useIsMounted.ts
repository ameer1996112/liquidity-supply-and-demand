import { useState, useEffect } from 'react';

/**
 * Returns `true` after the component has mounted on the client.
 * On the server (SSR), this always returns `false`.
 *
 * Use this to safely render dynamic content that would differ between
 * server and client (e.g. `new Date().toLocaleString()`), preventing
 * React Hydration Error #418.
 */
export function useIsMounted(): boolean {
  const [mounted, setMounted] = useState(false);

  useEffect(() => {
    // eslint-disable-next-line
    setMounted(true);
  }, []);

  return mounted;
}
