import { get } from "@core/api";
import type { OrderInfo } from "./types";

export const ordersApi = {
  list: (status?: string) => get<OrderInfo[]>(`/api/v1/orders${status ? `?status=${status}` : ""}`),
};
