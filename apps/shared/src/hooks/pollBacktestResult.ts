/**
 * Shared backtest polling logic — framework-agnostic.
 *
 * Both web and mobile hooks delegate polling to this function
 * so the backoff / timeout / progress logic lives in one place.
 */

import { backtest } from "../api/endpoints";
import type { BacktestResult, BacktestSummary } from "../types";

export interface PollOptions {
  /** Maximum time (ms) before giving up. Default 30 minutes. */
  timeoutMs?: number;
  /** Base delay (ms) for exponential backoff. Default 2000. */
  baseDelayMs?: number;
  /** Maximum delay (ms) between polls. Default 30000. */
  maxDelayMs?: number;
  /** Called on each poll with progress info (if available). */
  onProgress?: (current: number, total: number) => void;
  /** Return true to abort polling (e.g. component unmounted). */
  shouldAbort?: () => boolean;
}

export interface PollSuccess {
  status: "completed";
  result: BacktestResult;
}

export interface PollFailure {
  status: "failed" | "timeout" | "aborted";
}

export type PollOutcome = PollSuccess | PollFailure;

/**
 * Submit a backtest request and poll until it completes, fails, or times out.
 */
export async function pollBacktestResult(
  summary: BacktestSummary,
  opts: PollOptions = {},
): Promise<PollOutcome> {
  const {
    timeoutMs = 30 * 60 * 1000,
    baseDelayMs = 2000,
    maxDelayMs = 30_000,
    onProgress,
    shouldAbort,
  } = opts;

  const pollStart = Date.now();
  let status = summary.status;
  let attempt = 0;

  while (status === "running") {
    if (shouldAbort?.()) return { status: "aborted" };

    if (Date.now() - pollStart > timeoutMs) {
      return { status: "timeout" };
    }

    const delay = Math.min(baseDelayMs * 2 ** attempt, maxDelayMs);
    attempt++;
    await new Promise((r) => setTimeout(r, delay));

    if (shouldAbort?.()) return { status: "aborted" };

    const s = await backtest.status(summary.task_id);
    status = s.status;

    if (s.progress_current != null && s.progress_total != null && onProgress) {
      onProgress(s.progress_current, s.progress_total);
    }
  }

  if (shouldAbort?.()) return { status: "aborted" };

  if (status === "completed") {
    const result = await backtest.result(summary.task_id);
    return { status: "completed", result };
  }

  return { status: "failed" };
}
