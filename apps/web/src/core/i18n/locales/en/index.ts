import { common } from "./common";
import { dashboard } from "./dashboard";
import { portfolio } from "./portfolio";
import { strategies } from "./strategies";
import { orders } from "./orders";
import { backtest } from "./backtest";
import { risk } from "./risk";
import { settings } from "./settings";

export const en = {
  ...common,
  dashboard,
  portfolio,
  strategies,
  orders,
  backtest,
  risk,
  settings,
};

export type Translations = typeof en;
