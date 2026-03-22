import { get } from "@core/api";
import type { SystemStatus } from "./types";

export const systemApi = {
  health: () => get<{ status: string; version: string }>("/api/v1/system/health"),
  status: () => get<SystemStatus>("/api/v1/system/status"),
};
