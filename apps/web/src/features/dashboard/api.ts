/**
 * Re-export shared endpoints as feature-local names for the dashboard.
 */
import { portfolio, strategies } from "@quant/shared";

export const portfolioApi = portfolio;
export const strategiesApi = strategies;
