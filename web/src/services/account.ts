import { api } from "./api-client";

export type ProviderName = "deepseek" | "dashscope";
export type CredentialPurpose = "generation" | "embedding";

export interface ProviderCredential {
  id: string;
  provider: ProviderName;
  purpose: CredentialPurpose;
  version: number;
  status: "active" | "invalid" | "revoked";
  key_last_four: string;
  validated_at: string | null;
  last_used_at: string | null;
  created_at: string;
}

export interface UsageSnapshot {
  resources: Record<string, Record<string, { used: number; limit: number }>>;
  limits: Record<string, { used: number; limit: number }>;
  model_usage_month: {
    input_tokens: number;
    output_tokens: number;
    estimated_cost_usd: number;
    notice: string;
  };
  llm_limits: {
    task_max_tokens: number;
    monthly_reference_cost_usd: number;
  };
}

export function listProviderCredentials() {
  return api.get<{ items: ProviderCredential[] }>("/me/provider-credentials");
}

export function saveProviderCredential(input: {
  provider: ProviderName;
  purpose: CredentialPurpose;
  api_key: string;
}) {
  return api.post<ProviderCredential>("/me/provider-credentials", input);
}

export function validateProviderCredential(id: string) {
  return api.post<ProviderCredential>(`/me/provider-credentials/${id}/validate`);
}

export function revokeProviderCredential(id: string) {
  return api.delete<void>(`/me/provider-credentials/${id}`);
}

export function getUsage() {
  return api.get<UsageSnapshot>("/me/usage");
}

export function updateUsageLimits(input: {
  task_max_tokens?: number;
  monthly_reference_cost_usd?: number;
}) {
  return api.put<{ limits: Record<string, number> }>("/me/usage-limits", input);
}

export function recordModelProcessingConsent(policyVersion = "2026-09-14") {
  return api.post<{ policy: string; policy_version: string; accepted: boolean }>("/me/consents", {
    policy: "model_processing",
    policy_version: policyVersion,
    accepted: true,
  });
}

export function getTotpStatus() {
  return api.get<{ enabled: boolean; confirmed_at: string | null }>("/me/mfa/totp");
}

export function setupTotp() {
  return api.post<{ secret: string; otpauth_uri: string }>("/me/mfa/totp/setup");
}

export function confirmTotp(code: string) {
  return api.post<{ enabled: boolean; confirmed_at: string }>("/me/mfa/totp/confirm", { code });
}

export function disableTotp(code: string) {
  return api.delete<void>("/me/mfa/totp", { code });
}

export function exportAccountData() {
  return api.get<Record<string, unknown>>("/me/export");
}

export function requestAccountDeletion() {
  return api.post<{ status: string; execute_after: string }>("/me/deletion-request");
}
