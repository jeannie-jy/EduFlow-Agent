/** Cross-module notification used when the server rejects the current session. */

export const AUTH_STATE_CHANGED_EVENT = "eduflow-auth-state-changed";
const AUTH_KEY = "eduflow-auth";

export function notifyAuthStateChanged(): void {
  if (typeof window !== "undefined") {
    window.dispatchEvent(new Event(AUTH_STATE_CHANGED_EVENT));
  }
}

/** Remove the client-side hint after a server-side session has expired/revoked. */
export function expirePersistedAuthState(): void {
  try {
    localStorage.removeItem(AUTH_KEY);
  } catch {
    // 存储不可用 — 仍然通知内存中的认证状态刷新
  }
  notifyAuthStateChanged();
}
