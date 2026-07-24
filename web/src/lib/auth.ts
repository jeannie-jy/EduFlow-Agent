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
