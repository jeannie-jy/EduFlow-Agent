import { useEffect, useState } from "react";
import { CheckIcon, KeyRoundIcon, PencilIcon, RefreshCwIcon, ShieldCheckIcon, Trash2Icon } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { changePassword } from "@/features/auth/auth";
import { ApiError } from "@/services/api-client";
import {
  getUsage,
  activateProviderCredential,
  exportAccountData,
  listProviderCredentials,
  revokeProviderCredential,
  requestAccountDeletion,
  saveProviderCredential,
  updateProviderCredential,
  validateProviderCredential,
  updateUsageLimits,
  confirmTotp,
  disableTotp,
  getTotpStatus,
  setupTotp,
  type CredentialPurpose,
  type ProviderCredential,
  type ProviderName,
  type UsageSnapshot,
} from "@/services/account";

const PROVIDER_DEFAULTS: Record<ProviderName, { label: string; model: string; baseUrl: string }> = {
  deepseek: { label: "DeepSeek", model: "deepseek-chat", baseUrl: "https://api.deepseek.com/v1" },
  dashscope: { label: "阿里云百炼", model: "qwen-plus", baseUrl: "https://dashscope.aliyuncs.com/compatible-mode/v1" },
  openai: { label: "OpenAI", model: "gpt-4.1-mini", baseUrl: "https://api.openai.com/v1" },
  ollama: { label: "本地 Ollama", model: "llama3.2", baseUrl: "http://localhost:11434/v1" },
};

function defaultModel(provider: ProviderName, purpose: CredentialPurpose): string {
  if (purpose === "generation") return PROVIDER_DEFAULTS[provider].model;
  if (provider === "dashscope") return "text-embedding-v4";
  if (provider === "openai") return "text-embedding-3-small";
  if (provider === "ollama") return "nomic-embed-text";
  return PROVIDER_DEFAULTS.deepseek.model;
}

const CREDENTIAL_SECTIONS: Array<{
  purpose: CredentialPurpose;
  title: string;
  description: string;
}> = [
  {
    purpose: "generation",
    title: "内容生成",
    description: "用于生成教学内容、项目结构和反馈修订。",
  },
  {
    purpose: "embedding",
    title: "语义检索",
    description: "用于知识库语义检索；未配置时会降级为关键词匹配。",
  },
];

export function AccountSettingsPage() {
  const [credentials, setCredentials] = useState<ProviderCredential[]>([]);
  const [usage, setUsage] = useState<UsageSnapshot | null>(null);
  const [provider, setProvider] = useState<ProviderName>("deepseek");
  const [purpose, setPurpose] = useState<CredentialPurpose>("generation");
  const [connectionName, setConnectionName] = useState("DeepSeek");
  const [model, setModel] = useState(PROVIDER_DEFAULTS.deepseek.model);
  const [baseUrl, setBaseUrl] = useState(PROVIDER_DEFAULTS.deepseek.baseUrl);
  const [apiKey, setApiKey] = useState("");
  const [editingCredentialId, setEditingCredentialId] = useState<string | null>(null);
  const [pending, setPending] = useState(false);
  const [validatingCredentialId, setValidatingCredentialId] = useState<string | null>(null);
  const [revokingCredentialId, setRevokingCredentialId] = useState<string | null>(null);
  const [message, setMessage] = useState("");
  const [credentialMessage, setCredentialMessage] = useState("");
  const [taskMaxTokens, setTaskMaxTokens] = useState("");
  const [totpEnabled, setTotpEnabled] = useState(false);
  const [totpSecret, setTotpSecret] = useState("");
  const [totpCode, setTotpCode] = useState("");
  const [currentPassword, setCurrentPassword] = useState("");
  const [newPassword, setNewPassword] = useState("");

  const refresh = async () => {
    const [credentialResult, usageResult, totpResult] = await Promise.all([
      listProviderCredentials(), getUsage(), getTotpStatus(),
    ]);
    // Revoked credentials remain persisted for audit/export, but are not part
    // of the user's current model connections.
    setCredentials(credentialResult.items.filter((item) => item.status !== "revoked"));
    setUsage(usageResult);
    setTaskMaxTokens(String(usageResult.llm_limits.task_max_tokens));
    setTotpEnabled(totpResult.enabled);
  };

  useEffect(() => { void refresh(); }, []);

  const resetEditor = () => {
    setEditingCredentialId(null);
    setProvider("deepseek");
    setPurpose("generation");
    setConnectionName(PROVIDER_DEFAULTS.deepseek.label);
    setModel(PROVIDER_DEFAULTS.deepseek.model);
    setBaseUrl(PROVIDER_DEFAULTS.deepseek.baseUrl);
    setApiKey("");
  };

  const save = async (makeActive: boolean) => {
    if (!editingCredentialId && !apiKey.trim()) return;
    setPending(true);
    setMessage("");
    try {
      if (editingCredentialId) {
        await updateProviderCredential(editingCredentialId, {
          name: connectionName, provider, purpose, model, base_url: baseUrl,
          ...(apiKey.trim() ? { api_key: apiKey } : {}),
        });
        if (makeActive) await activateProviderCredential(editingCredentialId);
      } else {
        await saveProviderCredential({
          name: connectionName, provider, purpose, model, base_url: baseUrl,
          api_key: apiKey, make_active: makeActive,
        });
      }
      resetEditor();
      setMessage(makeActive ? "连接已保存并设为当前使用。" : "连接已加密保存，当前使用项未改变。");
      await refresh();
    } catch (error) {
      setMessage(error instanceof ApiError
        ? `保存失败：${error.message}`
        : "保存失败。请检查连接信息和密钥加密服务配置。");
    } finally {
      setPending(false);
    }
  };

  const validateCredential = async (id: string) => {
    setValidatingCredentialId(id);
    setCredentialMessage("正在验证连接…");
    try {
      const validated = await validateProviderCredential(id);
      setCredentials((current) => current.map((item) => item.id === id ? validated : item));
      setCredentialMessage("连接验证成功，当前密钥可以使用。");
    } catch (error) {
      await refresh().catch(() => undefined);
      if (error instanceof ApiError && error.status === 422) {
        setCredentialMessage("连接验证失败：供应商拒绝了这枚密钥，请检查 API Key 是否正确。");
      } else if (error instanceof ApiError && error.status === 503) {
        setCredentialMessage("连接验证暂时不可用，可能是供应商或服务端网络问题，请稍后重试。");
      } else if (error instanceof ApiError && error.status === 401) {
        setCredentialMessage("登录状态已过期，请重新登录后再验证。");
      } else {
        setCredentialMessage("连接验证失败，请稍后重试。");
      }
    } finally {
      setValidatingCredentialId(null);
    }
  };

  const beginEdit = (item: ProviderCredential) => {
    setEditingCredentialId(item.id);
    setConnectionName(item.name);
    setProvider(item.provider);
    setPurpose(item.purpose);
    setModel(item.model);
    setBaseUrl(item.base_url);
    setApiKey("");
    window.scrollTo({ top: 0, behavior: "smooth" });
  };

  const activateCredential = async (item: ProviderCredential) => {
    setCredentialMessage("正在切换当前连接…");
    try {
      await activateProviderCredential(item.id);
      setCredentials((current) => current.map((credential) => ({
        ...credential,
        is_active: credential.purpose === item.purpose
          ? credential.id === item.id
          : credential.is_active,
      })));
      setCredentialMessage(`已切换到“${item.name}”。`);
    } catch {
      setCredentialMessage("切换失败；无效或已删除的连接不能设为当前使用。");
    }
  };

  const revokeCredential = async (id: string) => {
    setRevokingCredentialId(id);
    setCredentialMessage("正在撤销接入…");
    try {
      await revokeProviderCredential(id);
      // Update immediately after the server confirms the state change. This
      // keeps the list correct even if a subsequent refresh is delayed.
      setCredentials((current) => current.filter((item) => item.id !== id));
      setCredentialMessage("接入已撤销。");
    } catch {
      setCredentialMessage("撤销失败，请稍后重试。");
    } finally {
      setRevokingCredentialId(null);
    }
  };

  return (
    <div className="mx-auto max-w-4xl space-y-8 p-6">
      <header>
        <h1 className="flex items-center gap-2 text-2xl font-semibold"><KeyRoundIcon />模型接入与用量</h1>
        <p className="mt-2 text-sm text-muted-foreground">EduFlow 使用你自己的模型账户，供应商账单是最终费用依据。</p>
      </header>

      <section className="rounded-xl border bg-card p-5">
        <div className="mb-5 flex gap-3 rounded-lg border border-amber-300/60 bg-amber-50 p-4 text-sm text-amber-950">
          <ShieldCheckIcon className="mt-0.5 size-5 shrink-0" />
          <p>密钥通过 HTTPS 提交并在服务端加密保存，不会写入浏览器存储，也不会显示明文。运行任务时服务端可临时解密，因此这不是端到端加密。教学主题、选中的材料片段和提示内容会发送给所选供应商。</p>
        </div>
        <form onSubmit={(event) => { event.preventDefault(); void save(false); }} className="grid gap-4 md:grid-cols-2">
          <div className="space-y-2">
            <Label htmlFor="connection-name">连接名称</Label>
            <Input id="connection-name" value={connectionName} onChange={(e) => setConnectionName(e.target.value)} placeholder="例如：生产环境 DeepSeek" />
          </div>
          <div className="space-y-2">
            <Label htmlFor="provider">供应商</Label>
            <select id="provider" className="h-10 w-full rounded-md border bg-background px-3" value={provider} onChange={(e) => {
              const next = e.target.value as ProviderName;
              const nextPurpose = next === "deepseek" ? "generation" : purpose;
              setProvider(next);
              setPurpose(nextPurpose);
              setConnectionName(PROVIDER_DEFAULTS[next].label);
              setModel(defaultModel(next, nextPurpose));
              setBaseUrl(PROVIDER_DEFAULTS[next].baseUrl);
            }}>
              <option value="deepseek">DeepSeek</option>
              <option value="dashscope">阿里百炼</option>
              <option value="openai">OpenAI</option>
              <option value="ollama">本地 Ollama</option>
            </select>
          </div>
          <div className="space-y-2">
            <Label htmlFor="purpose">用途</Label>
            <select id="purpose" className="h-10 w-full rounded-md border bg-background px-3" value={purpose} onChange={(e) => {
              const next = e.target.value as CredentialPurpose;
              setPurpose(next);
              setModel(defaultModel(provider, next));
            }}>
              <option value="generation">内容生成</option>
              {provider !== "deepseek" ? <option value="embedding">语义检索</option> : null}
            </select>
          </div>
          <div className="space-y-2">
            <Label htmlFor="provider-model">模型</Label>
            <Input id="provider-model" value={model} onChange={(e) => setModel(e.target.value)} placeholder="模型名称" />
          </div>
          <div className="space-y-2 md:col-span-2">
            <Label htmlFor="provider-base-url">Base URL</Label>
            <Input id="provider-base-url" value={baseUrl} onChange={(e) => setBaseUrl(e.target.value)} />
          </div>
          <div className="space-y-2">
            <Label htmlFor="provider-key">API Key</Label>
            <Input id="provider-key" type="password" autoComplete="off" value={apiKey} onChange={(e) => setApiKey(e.target.value)} placeholder={editingCredentialId ? "留空则保留现有密钥" : "仅在此处输入，不会再次显示"} />
          </div>
          <div className="flex flex-wrap items-end gap-2">
            <Button type="submit" variant="outline" disabled={pending || (!editingCredentialId && apiKey.trim().length < 8)}>{pending ? "保存中…" : "保存"}</Button>
            <Button type="button" disabled={pending || (!editingCredentialId && apiKey.trim().length < 8)} onClick={() => void save(true)}>保存并设为当前使用</Button>
            {editingCredentialId ? <Button type="button" variant="ghost" onClick={resetEditor}>取消编辑</Button> : null}
          </div>
        </form>
        {message ? <p className="mt-3 text-sm text-muted-foreground" role="status">{message}</p> : null}
      </section>

      <section className="rounded-xl border bg-card p-5">
        <h2 className="flex items-center gap-2 text-lg font-medium"><ShieldCheckIcon className="size-5" />管理员 MFA（TOTP）</h2>
        <p className="mt-1 text-sm text-muted-foreground">管理员账号启用后，登录必须输入身份验证器的一次性验证码。</p>
        {totpEnabled ? <div className="mt-4 flex flex-wrap items-end gap-3">
          <div className="space-y-2"><Label htmlFor="disable-totp-code">当前验证码</Label><Input id="disable-totp-code" inputMode="numeric" value={totpCode} onChange={(event) => setTotpCode(event.target.value)} /></div>
          <Button variant="outline" onClick={() => void disableTotp(totpCode).then(() => { setTotpEnabled(false); setTotpCode(""); setMessage("TOTP 已关闭"); })}>关闭 TOTP</Button>
        </div> : <div className="mt-4 space-y-3">
          <Button variant="outline" onClick={() => void setupTotp().then((result) => { setTotpSecret(result.secret); setMessage("请将密钥录入身份验证器，再输入当前验证码确认"); })}>生成 TOTP 密钥</Button>
          {totpSecret ? <div className="flex flex-wrap items-end gap-3"><div className="space-y-2"><Label htmlFor="totp-secret">一次性密钥</Label><Input id="totp-secret" readOnly value={totpSecret} /></div><div className="space-y-2"><Label htmlFor="confirm-totp-code">身份验证器验证码</Label><Input id="confirm-totp-code" inputMode="numeric" value={totpCode} onChange={(event) => setTotpCode(event.target.value)} /></div><Button onClick={() => void confirmTotp(totpCode).then(() => { setTotpEnabled(true); setTotpSecret(""); setTotpCode(""); setMessage("TOTP 已启用"); })}>确认启用</Button></div> : null}
        </div>}
      </section>

      <section className="rounded-xl border bg-card p-5">
        <h2 className="text-lg font-medium">修改密码</h2>
        <p className="mt-1 text-sm text-muted-foreground">修改后所有设备上的旧会话都会失效，需要重新登录。</p>
        <form className="mt-4 grid gap-3 sm:grid-cols-[1fr_1fr_auto] sm:items-end" onSubmit={(event) => {
          event.preventDefault();
          if (!currentPassword || newPassword.length < 8) return;
          void changePassword(currentPassword, newPassword).then(() => {
            setCurrentPassword("");
            setNewPassword("");
            setMessage("密码已修改，请重新登录");
          }).catch(() => setMessage("密码修改失败，请确认当前密码和新密码格式"));
        }}>
          <div className="space-y-2"><Label htmlFor="current-password">当前密码</Label><Input id="current-password" type="password" autoComplete="current-password" value={currentPassword} onChange={(event) => setCurrentPassword(event.target.value)} /></div>
          <div className="space-y-2"><Label htmlFor="new-password">新密码</Label><Input id="new-password" type="password" autoComplete="new-password" value={newPassword} onChange={(event) => setNewPassword(event.target.value)} /></div>
          <Button type="submit" variant="outline" disabled={!currentPassword || newPassword.length < 8}>修改密码</Button>
        </form>
      </section>

      <section className="rounded-xl border bg-card p-5">
        <h2 className="mb-4 text-lg font-medium">已保存的接入</h2>
        <div className="space-y-3">
          {CREDENTIAL_SECTIONS.map((section) => {
            const items = credentials.filter((item) => item.purpose === section.purpose);
            const hasActive = items.some((item) => item.is_active);
            return <div key={section.purpose} className="rounded-lg border p-4">
              <div className="mb-3">
                <h3 className="font-medium">{section.title}</h3>
                <p className="mt-1 text-sm text-muted-foreground">{section.description}</p>
              </div>
              {items.length ? <div className="space-y-3">{items.map((item) => (
                <div key={item.id} className="flex flex-wrap items-center justify-between gap-3 rounded-md border bg-background p-3">
                  <div className="min-w-0">
                    <div className="flex flex-wrap items-center gap-2">
                      <p className="font-medium">{item.name}</p>
                      {item.is_active ? <span className="rounded-full bg-emerald-100 px-2 py-0.5 text-xs font-medium text-emerald-800">当前使用</span> : null}
                    </div>
                    <p className="mt-1 text-xs text-muted-foreground">{PROVIDER_DEFAULTS[item.provider].label} · {item.model}</p>
                    <p className="truncate text-xs text-muted-foreground">{item.base_url}</p>
                    <p className="text-xs text-muted-foreground">sk-****{item.key_last_four} · {item.status === "valid" ? "验证通过" : item.status === "invalid" ? "验证失败" : "尚未验证"}</p>
                    <p className="text-xs text-muted-foreground">
                      {item.validated_at ? `最近验证：${new Date(item.validated_at).toLocaleString("zh-CN")}` : "尚未验证"}
                    </p>
                  </div>
                  <div className="flex flex-wrap gap-2">
                    {!item.is_active ? <Button size="sm" onClick={() => void activateCredential(item)} disabled={item.status === "invalid"}>
                      <CheckIcon />设为当前使用
                    </Button> : null}
                    <Button variant="outline" size="sm" onClick={() => beginEdit(item)}>
                      <PencilIcon />编辑
                    </Button>
                    <Button
                      variant="outline"
                      size="sm"
                      disabled={validatingCredentialId !== null}
                      onClick={() => void validateCredential(item.id)}
                    >
                      <RefreshCwIcon />{validatingCredentialId === item.id ? "验证中…" : "验证"}
                    </Button>
                    <Button
                      variant="outline"
                      size="sm"
                      disabled={revokingCredentialId !== null}
                      onClick={() => void revokeCredential(item.id)}
                    >
                      <Trash2Icon />{revokingCredentialId === item.id ? "删除中…" : "删除"}
                    </Button>
                  </div>
                </div>
              ))}</div> : <p className="text-sm text-muted-foreground">
                {section.purpose === "generation" ? "尚未配置。开始生成前必须添加“内容生成”密钥。" : "尚未配置语义检索接入。"}
              </p>}
              {section.purpose === "embedding" && !hasActive ? <div className="mt-3 rounded-lg border border-amber-300/60 bg-amber-50 p-3 text-sm text-amber-950">
                尚未选择语义检索连接。知识库检索会降级为关键词匹配；保存连接后还需将其设为当前使用。
              </div> : null}
            </div>;
          })}
        </div>
        {credentialMessage ? <p className="mt-3 text-sm text-muted-foreground" role="status" aria-live="polite">{credentialMessage}</p> : null}
      </section>

      {usage ? <section className="rounded-xl border bg-card p-5">
        <h2 className="text-lg font-medium">API 使用情况</h2>
        <p className="mt-1 text-sm text-muted-foreground">内容生成使用您当前启用的 API 连接。</p>
        <p className="mt-4 text-xs text-muted-foreground">本月经 EduFlow 调用的模型 Token：{(usage.model_usage_month.input_tokens + usage.model_usage_month.output_tokens).toLocaleString()}；参考费用 ${usage.model_usage_month.estimated_cost_usd.toFixed(4)}。最终用量和费用以 API 服务商账单为准。</p>
        <form className="mt-5 flex flex-wrap items-end gap-3" onSubmit={(event) => {
          event.preventDefault();
          void updateUsageLimits({
            task_max_tokens: Number(taskMaxTokens),
          }).then(() => { setMessage("单任务安全上限已更新"); return refresh(); }).catch(() => setMessage("安全上限更新失败"));
        }}>
          <div className="min-w-64 flex-1 space-y-2"><Label htmlFor="task-max-tokens">单任务 Token 安全上限</Label><Input id="task-max-tokens" type="number" min={1} max={10000000} value={taskMaxTokens} onChange={(event) => setTaskMaxTokens(event.target.value)} /></div>
          <Button type="submit" variant="outline">保存安全设置</Button>
        </form>
        <p className="mt-2 text-xs text-muted-foreground">该设置只防止单次任务异常消耗，不限制生成次数。</p>
      </section> : null}

      <section className="rounded-xl border bg-card p-5">
        <h2 className="text-lg font-medium">数据与账户</h2>
        <p className="mt-1 text-sm text-muted-foreground">可导出账户元数据与项目内容。注销申请有 7 天冷静期，并会立即撤销现有登录会话。</p>
        <div className="mt-4 flex flex-wrap gap-2">
          <Button variant="outline" onClick={() => void exportAccountData().then((data) => {
            const url = URL.createObjectURL(new Blob([JSON.stringify(data, null, 2)], { type: "application/json" }));
            const anchor = document.createElement("a");
            anchor.href = url;
            anchor.download = "eduflow-account-export.json";
            anchor.click();
            URL.revokeObjectURL(url);
          })}>导出我的数据</Button>
          <Button variant="destructive" onClick={() => {
            if (!window.confirm("确认申请注销？所有当前会话会立即失效，数据将在 7 天后删除。")) return;
            void requestAccountDeletion().then((result) => setMessage(`注销已安排：${new Date(result.execute_after).toLocaleString("zh-CN")}`));
          }}>申请注销账户</Button>
        </div>
      </section>
    </div>
  );
}
