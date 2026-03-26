import { get, post, put, del } from "@core/api";
import type { UserInfo } from "@core/api";

export const adminApi = {
  listUsers: () => get<UserInfo[]>("/api/v1/admin/users"),
  createUser: (data: { username: string; display_name: string; password: string; role: string }) =>
    post<UserInfo>("/api/v1/admin/users", data),
  updateUser: (id: number, data: { display_name?: string; role?: string; is_active?: boolean }) =>
    put<UserInfo>(`/api/v1/admin/users/${id}`, data),
  deleteUser: (id: number) => del<{ message: string }>(`/api/v1/admin/users/${id}`),
  resetPassword: (id: number, newPassword: string) =>
    post<{ message: string }>(`/api/v1/admin/users/${id}/reset-password`, { new_password: newPassword }),
};
