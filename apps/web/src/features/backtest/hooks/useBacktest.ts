import { useState, useRef, useEffect } from "react";
import { backtestApi } from "../api";
import { useT } from "@core/i18n";
import { pollBacktestResult } from "@quant/shared";
import type { BacktestRequest, BacktestResult } from "@quant/shared";

export function useBacktest() {
  const { t } = useT();
  const [running, setRunning] = useState(false);
  const [result, setResult] = useState<BacktestResult | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [progress, setProgress] = useState<{ current: number; total: number } | null>(null);
  const mountedRef = useRef(true);

  useEffect(() => {
    mountedRef.current = true;
    return () => { mountedRef.current = false; };
  }, []);

  const submit = async (form: BacktestRequest): Promise<BacktestResult | null> => {
    if (form.initial_cash <= 0 || form.universe.length === 0 || !form.strategy.trim()) return null;

    setRunning(true);
    setError(null);
    setResult(null);
    setProgress(null);
    try {
      const summary = await backtestApi.submit(form);

      const outcome = await pollBacktestResult(summary, {
        timeoutMs: 30 * 60 * 1000,
        baseDelayMs: 2000,
        onProgress: (current, total) => {
          if (mountedRef.current) setProgress({ current, total });
        },
        shouldAbort: () => !mountedRef.current,
      });

      if (!mountedRef.current) return null;

      if (outcome.status === "completed") {
        setResult(outcome.result);
        return outcome.result;
      } else if (outcome.status === "timeout") {
        setError(t.backtest.timedOut);
      } else if (outcome.status === "failed") {
        setError(t.backtest.failed);
      }
    } catch (err) {
      if (mountedRef.current) {
        setError(err instanceof Error ? err.message : t.common.requestFailed);
      }
    } finally {
      if (mountedRef.current) {
        setRunning(false);
        setProgress(null);
      }
    }
    return null;
  };

  return { running, result, error, progress, submit };
}
