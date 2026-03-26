/**
 * Thin wrapper around shared orders endpoints.
 * The web UI supports more filter values than the shared type,
 * so we widen the `status` parameter here.
 */
import { get, post, put, del } from "@core/api";
import type { OrderInfo, ManualOrderRequest } from "@core/api";

export const ordersApi = {
  list: (status?: string) =>
    get<OrderInfo[]>(`/api/v1/orders${status ? `?status=${status}` : ""}`),
  create: (req: ManualOrderRequest) =>
    post<OrderInfo>("/api/v1/orders", req),
  update: (orderId: string, data: { price?: number; quantity?: number }) =>
    put<OrderInfo>(`/api/v1/orders/${orderId}`, data),
  cancel: (orderId: string) =>
    del<OrderInfo>(`/api/v1/orders/${orderId}`),
};
