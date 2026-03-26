import { useState, useRef, useEffect } from "react";
import { alphaApi } from "../api";
import { useT } from "@core/i18n";
import type { AlphaRunRequest, AlphaReport } from "@core/api";

export function useAlphaResearch() {
  const { t } = useT();
  const [running, setRunning] = useState(false);
  const [result, setResult] = useState<AlphaReport | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [progress, setProgress] = useState<{ current: number; total: number } | null>(null);
  const mountedRef = useRef(true);

  useEffect(() => {
    mountedRef.current = true;
    return () => { mountedRef.current = false; };
  }, []);

  const submit = async (req: AlphaRunRequest): Promise<AlphaReport | null> => {
    setRunning(true);
    setError(null);
    setResult(null);
    setProgress(null);

    try {
      const summary = await alphaApi.run(req);
      const timeoutMs = 30 * 60 * 1000;
      const deadline = Date.now() + timeoutMs;
      let delay = 2000;

      while (mountedRef.current) {
        if (Date.now() > deadline) {
          if (mountedRef.current) setError(t.alpha.timedOut);
          return null;
        }
        await new Promise((r) => setTimeout(r, delay));
        delay = Math.min(delay * 1.3, 8000);

        if (!mountedRef.current) return null;
        const status = await alphaApi.status(summary.task_id);

        if (status.progress_current != null && status.progress_total != null) {
          if (mountedRef.current) setProgress({ current: status.progress_current, total: status.progress_total });
        }

        if (status.status === "completed") {
          const report = await alphaApi.result(summary.task_id);
          if (mountedRef.current) setResult(report);
          return report;
        }
        if (status.status === "failed") {
          if (mountedRef.current) setError(status.error ?? t.alpha.failed);
          return null;
        }
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
