import { getJson } from "@/api/http";
import type { AdminOverviewRead, AdminRunMonitorRead, AuditLogListRead, AuditLogStatsRead } from "@/api/types";


export interface AuditLogListParams {
  page?: number;
  page_size?: number;
  actor_user_id?: number;
  category?: string;
  success?: boolean;
  start_at?: string;
  end_at?: string;
}

export interface AuditLogStatsParams {
  actor_user_id?: number;
  category?: string;
  success?: boolean;
  start_at?: string;
  end_at?: string;
}

export interface AdminRunsMonitorParams {
  limit?: number;
}

export function fetchAdminOverview() {
  return getJson<AdminOverviewRead>("/api/admin/overview");
}

export function fetchAdminAuditLogs(params: AuditLogListParams = {}) {
  return getJson<AuditLogListRead>("/api/admin/audit-logs", params);
}

export function fetchAdminAuditLogStats(params: AuditLogStatsParams = {}) {
  return getJson<AuditLogStatsRead>("/api/admin/audit-logs/stats", params);
}

export function fetchAdminRunsMonitor(params: AdminRunsMonitorParams = {}) {
  return getJson<AdminRunMonitorRead>("/api/admin/runs/monitor", params);
}
