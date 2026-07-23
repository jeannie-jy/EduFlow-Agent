/**
 * Auth 状态管理（最小可用单元）。
 *
 * 当前 MVP：auth 状态写入 localStorage，后续可替换为 React Context 或 Zustand。
 */

const AUTH_KEY = "eduflow_auth";

export interface AuthState {
  isAuthenticated: boolean;
  nickname: string;
  email: string;
}

export function setAuthState(state: AuthState): void {
  localStorage.setItem(AUTH_KEY, JSON.stringify(state));
}

export function getAuthState(): AuthState | null {
  try {
    const raw = localStorage.getItem(AUTH_KEY);
    return raw ? (JSON.parse(raw) as AuthState) : null;
  } catch {
    return null;
  }
}

export function clearAuthState(): void {
  localStorage.removeItem(AUTH_KEY);
}
