export interface OrderInfo {
  id: string;
  symbol: string;
  side: "BUY" | "SELL";
  quantity: number;
  price: number | null;
  status: string;
  filled_qty: number;
  filled_avg_price: number;
  commission: number;
  created_at: string;
  strategy_id: string;
}
