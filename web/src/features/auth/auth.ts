/** 认证表单校验与后端会话 API。 */

import { api } from "@/services/api-client";

export type LoginValues = {
  email: string;
  password: string;
  totp_code?: string;
};

export type RegistrationValues = {
  nickname: string;
  email: string;
  password: string;
  confirmation: string;
  acceptedTerms: boolean;
};

export type LoginErrors = Partial<Record<keyof LoginValues, string>>;
export type RegistrationErrors = Partial<Record<keyof RegistrationValues, string>>;

const emailPattern = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
const passwordPattern = /^(?=.*[A-Za-z])(?=.*\d).{8,}$/;

export function validateLogin(values: LoginValues): LoginErrors {
  const errors: LoginErrors = {};
  if (!values.email.trim()) errors.email = "请输入邮箱地址";
  else if (!emailPattern.test(values.email)) errors.email = "请输入有效的邮箱地址";
  if (!values.password) errors.password = "请输入密码";
  return errors;
}

export function validateRegistration(values: RegistrationValues): RegistrationErrors {
  const errors: RegistrationErrors = {};
  if (!values.nickname.trim()) errors.nickname = "请输入昵称";
  if (!values.email.trim()) errors.email = "请输入邮箱地址";
  else if (!emailPattern.test(values.email)) errors.email = "请输入有效的邮箱地址";
  if (!values.password) errors.password = "请输入密码";
  else if (!passwordPattern.test(values.password)) {
    errors.password = "密码需至少 8 位，并同时包含字母和数字";
  }
  if (!values.confirmation) errors.confirmation = "请再次输入密码";
  else if (values.confirmation !== values.password) errors.confirmation = "两次输入的密码不一致";
  if (!values.acceptedTerms) errors.acceptedTerms = "请阅读并同意服务条款";
  return errors;
}

export interface AuthUser {
  id: string;
  nickname: string;
  email: string;
  role: "student" | "teacher" | "admin";
  email_verified: boolean;
}

export function login(values: LoginValues): Promise<AuthUser> {
  return api.post<AuthUser>("/auth/login", values);
}

async function solveRegistrationChallenge(challenge: string, difficulty: number): Promise<string> {
  const encoded = challenge.split(".", 1)[0].replace(/-/g, "+").replace(/_/g, "/");
  const payload = atob(encoded + "=".repeat((4 - encoded.length % 4) % 4));
  const nonce = payload.split(".", 1)[0];
  const prefix = "0".repeat(difficulty);
  for (let attempt = 0; attempt < 2_000_000; attempt += 1) {
    const digest = await crypto.subtle.digest("SHA-256", new TextEncoder().encode(`${nonce}${attempt}`));
    const hash = Array.from(new Uint8Array(digest), (byte) => byte.toString(16).padStart(2, "0")).join("");
    if (hash.startsWith(prefix)) return String(attempt);
  }
  throw new Error("Registration challenge could not be solved");
}

export async function register(values: Omit<RegistrationValues, "confirmation" | "acceptedTerms">): Promise<AuthUser> {
  const challenge = await api.get<{ challenge: string; difficulty: number }>("/auth/registration-challenge");
  const solution = await solveRegistrationChallenge(challenge.challenge, challenge.difficulty);
  return api.post<AuthUser>("/auth/register", {
    ...values,
    accepted_terms: true,
    policy_version: "2026-09-14",
    registration_challenge: challenge.challenge,
    registration_solution: solution,
  });
}

export function getCurrentUser(): Promise<AuthUser> {
  return api.get<AuthUser>("/auth/me");
}

export function logout(): Promise<void> {
  return api.post<void>("/auth/logout");
}

export function requestEmailVerification(): Promise<{ status: string }> {
  return api.post("/auth/request-email-verification");
}

export function verifyEmail(token: string): Promise<{ status: string }> {
  return api.post("/auth/verify-email", { token });
}

export function forgotPassword(email: string): Promise<{ status: string }> {
  return api.post("/auth/forgot-password", { email });
}

export function resetPassword(token: string, password: string): Promise<{ status: string }> {
  return api.post("/auth/reset-password", { token, password });
}

export function changePassword(currentPassword: string, newPassword: string): Promise<{ status: string }> {
  return api.post("/auth/change-password", {
    current_password: currentPassword,
    new_password: newPassword,
  });
}
