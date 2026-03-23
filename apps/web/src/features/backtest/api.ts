import { get, post } from "@core/api";
import type { BacktestRequest, BacktestSummary, BacktestResult, StrategyInfo } from "@quant/shared";

export const backtestApi = {
  submit: (req: BacktestRequest) => post<BacktestSummary>("/api/v1/backtest", req),
  status: (id: string) => get<BacktestSummary>(`/api/v1/backtest/${id}`),
  result: (id: string) => get<BacktestResult>(`/api/v1/backtest/${id}/result`),
};

export const strategiesApi = {
  list: () => get<{ strategies: StrategyInfo[] }>("/api/v1/strategies").then((r) => r.strategies),
};
