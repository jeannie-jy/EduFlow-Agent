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
