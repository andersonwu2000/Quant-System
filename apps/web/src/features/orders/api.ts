import { get, post } from "@core/api";
import type { OrderInfo, ManualOrderRequest } from "@quant/shared";

export const ordersApi = {
  list: (status?: string) =>
    get<OrderInfo[]>(`/api/v1/orders${status ? `?status=${status}` : ""}`),
  create: (req: ManualOrderRequest) =>
    post<OrderInfo>("/api/v1/orders", req),
};
