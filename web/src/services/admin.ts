import { api } from "./api-client";

export type UserRole = "student" | "teacher" | "admin";

export interface AdminUser {
  id: string;
  email: string;
  nickname: string;
  role: UserRole;
  is_active: boolean;
  session_count: number;
  created_at: string | null;
}

export interface AdminUserPage {
  users: AdminUser[];
  next_cursor: string | null;
}

export interface AdminUserFilters {
  cursor?: string;
  role?: UserRole;
  is_active?: boolean;
  search?: string;
  limit?: number;
}

export interface AdminQuota {
  user_id: string;
  limits: Record<string, number>;
  is_suspended: boolean;
  usage: {
    resources: Record<string, Record<string, { used: number; limit: number }>>;
    limits: Record<string, { used: number; limit: number }>;
    model_usage_month: {
      input_tokens: number;
      output_tokens: number;
      estimated_cost_usd: number;
      notice: string;
    };
  };
}

export type AdminQuotaChange = Partial<{
  projects: number;
  material_bytes: number;
  artifact_bytes: number;
  generation_concurrent: number;
  video_concurrent: number;
  task_max_tokens: number;
  is_suspended: boolean;
}>;

export function listAdminUsers(filters: AdminUserFilters = {}): Promise<AdminUserPage> {
  const params: Record<string, string> = {};
  if (filters.cursor) params.cursor = filters.cursor;
  if (filters.role) params.role = filters.role;
  if (filters.is_active !== undefined) params.is_active = String(filters.is_active);
  if (filters.search) params.search = filters.search;
  if (filters.limit) params.limit = String(filters.limit);
  return api.get<AdminUserPage>("/admin/users", params);
}

export function updateAdminUser(
  userId: string,
  change: Partial<Pick<AdminUser, "role" | "is_active">>,
): Promise<AdminUser> {
  return api.patch<AdminUser>(`/admin/users/${userId}`, change);
}

export function revokeAdminUserSessions(userId: string): Promise<{ revoked: number }> {
  return api.delete<{ revoked: number }>(`/admin/users/${userId}/sessions`);
}

export function getAdminUserQuota(userId: string): Promise<AdminQuota> {
  return api.get<AdminQuota>(`/admin/users/${userId}/quota`);
}

export function updateAdminUserQuota(userId: string, change: AdminQuotaChange): Promise<AdminQuota> {
  return api.put<AdminQuota>(`/admin/users/${userId}/quota`, change).then(async () => getAdminUserQuota(userId));
}
