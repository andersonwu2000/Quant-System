import { useState, useRef, useEffect } from "react";
import { backtest } from "@quant/shared";
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
      const MAX_POLL_MS = 10 * 60 * 1000; // 10 min on mobile
      const pollStart = Date.now();
      let status = summary.status;
      while (status === "running" && mountedRef.current) {
        if (Date.now() - pollStart > MAX_POLL_MS) {
          setError("Backtest timed out");
          return;
        }
        await new Promise((r) => setTimeout(r, 3000));
        if (!mountedRef.current) break;
        const s = await backtest.status(summary.task_id);
        status = s.status;
        if (s.progress_current != null && s.progress_total != null) {
          setProgress({ current: s.progress_current, total: s.progress_total });
        }
      }
      if (!mountedRef.current) return;
      if (status === "completed") {
        const r = await backtest.result(summary.task_id);
        if (mountedRef.current) setResult(r);
      } else if (status === "failed") {
        if (mountedRef.current) setError("Backtest failed");
      }
    } catch (err) {
      if (mountedRef.current) setError(err instanceof Error ? err.message : "Request failed");
    } finally {
      if (mountedRef.current) { setRunning(false); setProgress(null); }
    }
  };

  return { running, result, error, progress, submit };
}
