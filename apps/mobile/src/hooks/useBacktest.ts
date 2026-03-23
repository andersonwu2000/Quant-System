import { useState, useRef, useEffect } from "react";
import { backtest, pollBacktestResult } from "@quant/shared";
import type { BacktestRequest, BacktestResult } from "@quant/shared";

export function useBacktest() {
  const [running, setRunning] = useState(false);
  const [result, setResult] = useState<BacktestResult | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [progress, setProgress] = useState<{ current: number; total: number } | null>(null);
  const mountedRef = useRef(true);

  useEffect(() => {
    mountedRef.current = true;
    return () => { mountedRef.current = false; };
  }, []);

  const submit = async (form: BacktestRequest) => {
    setRunning(true);
    setError(null);
    setResult(null);
    setProgress(null);
    try {
      const summary = await backtest.submit(form);

      const outcome = await pollBacktestResult(summary, {
        timeoutMs: 10 * 60 * 1000, // 10 min on mobile
        baseDelayMs: 3000,
        onProgress: (current, total) => {
          if (mountedRef.current) setProgress({ current, total });
        },
        shouldAbort: () => !mountedRef.current,
      });

      if (!mountedRef.current) return;

      if (outcome.status === "completed") {
        setResult(outcome.result);
      } else if (outcome.status === "timeout") {
        setError("Backtest timed out");
      } else if (outcome.status === "failed") {
        setError("Backtest failed");
      }
    } catch (err) {
      if (mountedRef.current) setError(err instanceof Error ? err.message : "Request failed");
    } finally {
      if (mountedRef.current) { setRunning(false); setProgress(null); }
    }
  };

  return { running, result, error, progress, submit };
}
