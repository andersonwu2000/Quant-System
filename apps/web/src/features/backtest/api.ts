/**
 * Re-export shared backtest endpoints as `backtestApi` for feature-local use.
 */
import { backtest } from "@quant/shared";

export const backtestApi = backtest;
