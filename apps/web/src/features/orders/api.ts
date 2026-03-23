/**
 * Thin wrapper around shared orders endpoints.
 * The web UI supports more filter values than the shared type,
 * so we widen the `status` parameter here.
 */
import { get, post } from "@core/api";
import type { OrderInfo, ManualOrderRequest } from "@quant/shared";

export const ordersApi = {
  list: (status?: string) =>
    get<OrderInfo[]>(`/api/v1/orders${status ? `?status=${status}` : ""}`),
  create: (req: ManualOrderRequest) =>
    post<OrderInfo>("/api/v1/orders", req),
};
