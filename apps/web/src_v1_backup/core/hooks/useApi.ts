import { useState, useEffect, useCallback, useRef } from "react";

/**
 * Generic data-fetching hook. The `fetcher` does NOT need to be memoized —
 * the latest reference is always called via a ref.
 *
 * Pass `deps` to re-fetch when external values change (e.g., a filter).
 */
export function useApi<T>(fetcher: () => Promise<T>, deps: unknown[] = []) {
  const [data, setData] = useState<T | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const mountedRef = useRef(true);
  const fetcherRef = useRef(fetcher);
  fetcherRef.current = fetcher;

  useEffect(() => {
    mountedRef.current = true;
    return () => { mountedRef.current = false; };
  }, []);

  const refresh = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const result = await fetcherRef.current();
      if (mountedRef.current) {
        setData(result);
        setError(null);
      }
    } catch (err) {
      if (mountedRef.current) {
        setError(err instanceof Error ? err.message : "Request failed");
      }
    } finally {
      if (mountedRef.current) {
        setLoading(false);
      }
    }
  }, []);

  // Initial fetch + re-fetch when deps change
  // eslint-disable-next-line react-hooks/exhaustive-deps
  useEffect(() => { refresh(); }, deps);

  return { data, loading, error, refresh, setData };
}
