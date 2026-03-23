import { useState, useCallback } from "react";
import type { BacktestResult, BacktestRequest } from "@quant/shared";

const STORAGE_KEY = "quant_backtest_history";
const MAX_ENTRIES = 20;

export interface BacktestHistoryEntry {
  id: string;
  timestamp: string;
  request: BacktestRequest;
  result: BacktestResult;
}

function loadHistory(): BacktestHistoryEntry[] {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    return raw ? JSON.parse(raw) : [];
  } catch {
    return [];
  }
}

function saveHistory(entries: BacktestHistoryEntry[]) {
  localStorage.setItem(STORAGE_KEY, JSON.stringify(entries.slice(0, MAX_ENTRIES)));
}

export function useBacktestHistory() {
  const [history, setHistory] = useState<BacktestHistoryEntry[]>(loadHistory);

  const addEntry = useCallback((request: BacktestRequest, result: BacktestResult) => {
    const entry: BacktestHistoryEntry = {
      id: Date.now().toString(36) + Math.random().toString(36).slice(2, 6),
      timestamp: new Date().toISOString(),
      request,
      result,
    };
    setHistory((prev) => {
      const next = [entry, ...prev].slice(0, MAX_ENTRIES);
      saveHistory(next);
      return next;
    });
  }, []);

  const removeEntry = useCallback((id: string) => {
    setHistory((prev) => {
      const next = prev.filter((e) => e.id !== id);
      saveHistory(next);
      return next;
    });
  }, []);

  const clearHistory = useCallback(() => {
    localStorage.removeItem(STORAGE_KEY);
    setHistory([]);
  }, []);

  return { history, addEntry, removeEntry, clearHistory };
}
