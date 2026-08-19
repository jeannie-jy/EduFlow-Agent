/**
 * Auth 状态管理（刻意占位实现）。
 *
 * 当前后端尚未实现认证（无 /api/auth/* 端点），MVP 用 localStorage 模拟登录态，
 * 仅供 UI 展示登录/工作台入口，**不可用于任何安全决策**。
 *
 * 真实方案（后端认证立项后落地）：
 * - HttpOnly cookie 会话 + GET /api/auth/me 验证当前用户
 * - 登录/注册端点换为真实表单提交，密码哈希与限流在后端完成
 * - 替换本模块所有调用点（LoginPage / RegisterPage / LandingPage）
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
