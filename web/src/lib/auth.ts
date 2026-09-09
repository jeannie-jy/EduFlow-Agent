/**
 * Auth UI 缓存。
 *
 * 登录凭据保存在服务端散列会话和 HttpOnly cookie 中；localStorage 只缓存昵称等
 * 展示信息，不能作为授权依据。业务 API 的最终授权由后端完成。
 */

const AUTH_KEY = "eduflow-auth";

export interface AuthState {
  id?: string;
  isAuthenticated: boolean;
  nickname: string;
  email: string;
  role?: "student" | "teacher" | "admin";
}

export function getAuthState(): AuthState | null {
  try {
    const raw = localStorage.getItem(AUTH_KEY);
    return raw ? (JSON.parse(raw) as AuthState) : null;
  } catch {
    return null;
  }
}

export function setAuthState(state: AuthState): void {
  try {
    localStorage.setItem(AUTH_KEY, JSON.stringify(state));
  } catch {
    // 存储不可用（无痕模式 / 配额满）— 静默降级
  }
}

export function clearAuthState(): void {
  try {
    localStorage.removeItem(AUTH_KEY);
  } catch {
    // 存储不可用 — 静默降级
  }
}
