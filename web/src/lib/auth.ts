/**
 * @deprecated 临时认证模块 — 当前仅用于 UI 状态的本地缓存（无服务端验证）。
 * 后端认证就绪后需替换为：HttpOnly cookie + /api/auth/me 验证。
 * 不要依赖 localStorage 中的 isAuthenticated 做安全决策。
 *
 * Auth 状态管理（最小可用单元）。
 *
 * 当前 MVP：auth 状态写入 localStorage，后续可替换为 React Context 或 Zustand。
 */

const AUTH_KEY = "eduflow-auth";

export interface AuthState {
  isAuthenticated: boolean;
  nickname: string;
  email: string;
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
