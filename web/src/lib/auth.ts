/**
 * Auth UI 缓存 and the server-session bootstrap.
 *
 * 登录凭据保存在服务端散列会话和 HttpOnly cookie 中；localStorage 只缓存昵称等
 * 展示信息，不能作为授权依据。业务 API 的最终授权由后端完成。
 */

import { createContext, createElement, useCallback, useContext, useEffect, useState, type PropsWithChildren } from "react";
import { api, ApiError } from "@/services/api-client";
import { AUTH_STATE_CHANGED_EVENT, expirePersistedAuthState, notifyAuthStateChanged } from "./auth-events";

const AUTH_KEY = "eduflow-auth";

export const AUTH_SESSION_UNAVAILABLE = "unavailable" as const;

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

export function setAuthState(state: AuthState, options?: { notify?: boolean }): void {
  try {
    localStorage.setItem(AUTH_KEY, JSON.stringify(state));
  } catch {
    // 存储不可用（无痕模式 / 配额满）— 静默降级
  }
  if (options?.notify !== false) notifyAuthStateChanged();
}

export function clearAuthState(): void {
  expirePersistedAuthState();
}

export interface AuthUser {
  id: string;
  nickname: string;
  email: string;
  role: "student" | "teacher" | "admin";
  email_verified: boolean;
}

function stateFromUser(user: AuthUser): AuthState {
  return {
    id: user.id,
    isAuthenticated: true,
    nickname: user.nickname,
    email: user.email,
    role: user.role,
  };
}

/** Confirm the HttpOnly session with the server and refresh the display cache. */
export async function refreshAuthSession(): Promise<AuthState> {
  const user = await api.get<AuthUser>("/auth/me");
  const state = stateFromUser(user);
  // Avoid feeding the successful bootstrap back into the validation effect.
  setAuthState(state, { notify: false });
  return state;
}

export function isUnauthorized(error: unknown): boolean {
  return error instanceof ApiError && error.status === 401;
}

export type AuthStatus = "ready" | "checking" | typeof AUTH_SESSION_UNAVAILABLE;

interface AuthContextValue {
  state: AuthState | null;
  status: AuthStatus;
  retry: () => void;
}

const AuthContext = createContext<AuthContextValue | null>(null);

/** Keep UI auth hints synchronized with the authoritative server session. */
export function AuthProvider({ children }: PropsWithChildren) {
  // Component tests intentionally own their mocked auth state. In a real
  // browser this flag is never set, so startup always confirms the cookie.
  const shouldValidateSession = import.meta.env.MODE !== "test";
  const [state, setState] = useState<AuthState | null>(() => getAuthState());
  const [status, setStatus] = useState<AuthStatus>(() => (
    shouldValidateSession && getAuthState()?.isAuthenticated ? "checking" : "ready"
  ));
  const [validationAttempt, setValidationAttempt] = useState(0);

  useEffect(() => {
    if (!shouldValidateSession) return;

    const handleAuthStateChanged = () => {
      const next = getAuthState();
      setState(next);
      if (next?.isAuthenticated) {
        setStatus("checking");
        setValidationAttempt((attempt) => attempt + 1);
      } else {
        setStatus("ready");
      }
    };

    window.addEventListener(AUTH_STATE_CHANGED_EVENT, handleAuthStateChanged);
    return () => window.removeEventListener(AUTH_STATE_CHANGED_EVENT, handleAuthStateChanged);
  }, [shouldValidateSession]);

  useEffect(() => {
    if (!shouldValidateSession) return;

    const cached = getAuthState();
    if (!cached?.isAuthenticated) {
      setState(null);
      setStatus("ready");
      return;
    }

    let cancelled = false;
    setState(cached);
    setStatus("checking");
    void refreshAuthSession()
      .then((next) => {
        if (cancelled) return;
        setState(next);
        setStatus("ready");
      })
      .catch((error: unknown) => {
        if (cancelled) return;
        if (isUnauthorized(error)) {
          expirePersistedAuthState();
          setState(null);
          setStatus("ready");
          return;
        }
        // A server/network outage must not be mistaken for a valid session.
        setStatus(AUTH_SESSION_UNAVAILABLE);
      });

    return () => {
      cancelled = true;
    };
  }, [shouldValidateSession, validationAttempt]);

  const retry = useCallback(() => {
    setValidationAttempt((attempt) => attempt + 1);
  }, []);

  return createElement(AuthContext.Provider, { value: { state, status, retry } }, children);
}

export function useAuth(): AuthContextValue {
  const context = useContext(AuthContext);
  if (!context) throw new Error("useAuth must be used within AuthProvider");
  return context;
}
