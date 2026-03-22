import { get } from "@core/api";
import type { Portfolio, StrategyInfo } from "@core/types";

export const portfolioApi = {
  get: () => get<Portfolio>("/api/v1/portfolio"),
};

export const strategiesApi = {
  list: () => get<{ strategies: StrategyInfo[] }>("/api/v1/strategies").then((r) => r.strategies),
};
