/**
 * @deprecated 临时认证模块 — 当前仅用于 UI 状态的本地缓存（无服务端验证）。
 * 后端认证就绪后需替换为：HttpOnly cookie + /api/auth/me 验证。
 * 不要依赖 localStorage 中的 isAuthenticated 做安全决策。
 */

export interface AuthState {
  isAuthenticated: boolean;
  nickname: string;
  email: string;
}

const AUTH_KEY = "eduflow-auth";

function getAuthState(): AuthState {
  try {
    const raw = localStorage.getItem(AUTH_KEY);
    if (raw) return JSON.parse(raw) as AuthState;
  } catch { /* corrupted */ }
  return { isAuthenticated: false, nickname: "", email: "" };
}

function setAuthState(state: AuthState): void {
  localStorage.setItem(AUTH_KEY, JSON.stringify(state));
}

function clearAuthState(): void {
  localStorage.removeItem(AUTH_KEY);
}

export { getAuthState, setAuthState, clearAuthState };
