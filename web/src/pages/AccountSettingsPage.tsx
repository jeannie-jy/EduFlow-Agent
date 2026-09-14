import { useEffect, useState } from "react";
import { KeyRoundIcon, RefreshCwIcon, ShieldCheckIcon, Trash2Icon } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { changePassword } from "@/features/auth/auth";
import {
  getUsage,
  exportAccountData,
  listProviderCredentials,
  revokeProviderCredential,
  requestAccountDeletion,
  saveProviderCredential,
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

export function AccountSettingsPage() {
  const [credentials, setCredentials] = useState<ProviderCredential[]>([]);
  const [usage, setUsage] = useState<UsageSnapshot | null>(null);
  const [provider, setProvider] = useState<ProviderName>("deepseek");
  const [purpose, setPurpose] = useState<CredentialPurpose>("generation");
  const [apiKey, setApiKey] = useState("");
  const [pending, setPending] = useState(false);
  const [message, setMessage] = useState("");
  const [taskMaxTokens, setTaskMaxTokens] = useState("");
  const [monthlyCost, setMonthlyCost] = useState("");
  const [totpEnabled, setTotpEnabled] = useState(false);
  const [totpSecret, setTotpSecret] = useState("");
  const [totpCode, setTotpCode] = useState("");
  const [currentPassword, setCurrentPassword] = useState("");
  const [newPassword, setNewPassword] = useState("");

  const refresh = async () => {
    const [credentialResult, usageResult, totpResult] = await Promise.all([
      listProviderCredentials(), getUsage(), getTotpStatus(),
    ]);
    setCredentials(credentialResult.items);
    setUsage(usageResult);
    setTaskMaxTokens(String(usageResult.llm_limits.task_max_tokens));
    setMonthlyCost(String(usageResult.llm_limits.monthly_reference_cost_usd));
    setTotpEnabled(totpResult.enabled);
  };

  useEffect(() => { void refresh(); }, []);

  const save = async (event: React.FormEvent) => {
    event.preventDefault();
    if (!apiKey.trim()) return;
    setPending(true);
    setMessage("");
    try {
      await saveProviderCredential({ provider, purpose, api_key: apiKey });
      setApiKey("");
      setMessage("密钥已加密保存。建议立即执行连接验证。");
      await refresh();
    } catch {
      setMessage("保存失败。请确认密钥加密服务已配置。");
    } finally {
      setPending(false);
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
        <form onSubmit={save} className="grid gap-4 md:grid-cols-[1fr_1fr_2fr_auto] md:items-end">
          <div className="space-y-2">
            <Label htmlFor="provider">供应商</Label>
            <select id="provider" className="h-10 w-full rounded-md border bg-background px-3" value={provider} onChange={(e) => {
              const next = e.target.value as ProviderName;
              setProvider(next);
              if (next === "deepseek") setPurpose("generation");
            }}>
              <option value="deepseek">DeepSeek</option>
              <option value="dashscope">阿里百炼</option>
            </select>
          </div>
          <div className="space-y-2">
            <Label htmlFor="purpose">用途</Label>
            <select id="purpose" className="h-10 w-full rounded-md border bg-background px-3" value={purpose} onChange={(e) => setPurpose(e.target.value as CredentialPurpose)}>
              <option value="generation">内容生成</option>
              {provider === "dashscope" ? <option value="embedding">语义检索</option> : null}
            </select>
          </div>
          <div className="space-y-2">
            <Label htmlFor="provider-key">API Key</Label>
            <Input id="provider-key" type="password" autoComplete="off" value={apiKey} onChange={(e) => setApiKey(e.target.value)} placeholder="仅在此处输入，不会再次显示" />
          </div>
          <Button type="submit" disabled={pending || apiKey.trim().length < 8}>{pending ? "保存中…" : "加密保存"}</Button>
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
        {!credentials.some((item) => item.purpose === "embedding" && item.status === "active") ? <div className="mb-4 rounded-lg border border-amber-300/60 bg-amber-50 p-3 text-sm text-amber-950">
          尚未配置阿里百炼 Embedding 密钥。知识库检索会降级为关键词匹配，相关性和教学 grounding 质量可能下降；配置后新任务会自动使用语义检索。
        </div> : null}
        <div className="space-y-3">
          {credentials.length === 0 ? <p className="text-sm text-muted-foreground">尚未配置。开始生成前必须添加“内容生成”密钥。</p> : credentials.map((item) => (
            <div key={item.id} className="flex flex-wrap items-center justify-between gap-3 rounded-lg border p-3">
              <div>
                <p className="font-medium">{item.provider === "deepseek" ? "DeepSeek" : "阿里百炼"} · {item.purpose === "generation" ? "内容生成" : "语义检索"}</p>
                <p className="text-xs text-muted-foreground">•••• {item.key_last_four} · v{item.version} · {item.status}</p>
              </div>
              {item.status !== "revoked" ? <div className="flex gap-2">
                <Button variant="outline" size="sm" onClick={() => void validateProviderCredential(item.id).then(refresh)}><RefreshCwIcon />验证</Button>
                <Button variant="outline" size="sm" onClick={() => void revokeProviderCredential(item.id).then(refresh)}><Trash2Icon />撤销</Button>
              </div> : null}
            </div>
          ))}
        </div>
      </section>

      {usage ? <section className="rounded-xl border bg-card p-5">
        <h2 className="mb-4 text-lg font-medium">本月平台用量</h2>
        <div className="grid gap-3 sm:grid-cols-2">
          {Object.entries(usage.resources).map(([resource, periods]) => <div key={resource} className="rounded-lg border p-3 text-sm">
            <p className="font-medium">{resource === "generation" ? "生成任务" : "视频任务"}</p>
            <p className="mt-1 text-muted-foreground">今日 {periods.day.used}/{periods.day.limit} · 本月 {periods.month.used}/{periods.month.limit}</p>
          </div>)}
        </div>
        <p className="mt-4 text-xs text-muted-foreground">本月模型 Token：{(usage.model_usage_month.input_tokens + usage.model_usage_month.output_tokens).toLocaleString()}；参考费用 ${usage.model_usage_month.estimated_cost_usd.toFixed(4)}。{usage.model_usage_month.notice}</p>
        <form className="mt-5 grid gap-3 sm:grid-cols-[1fr_1fr_auto] sm:items-end" onSubmit={(event) => {
          event.preventDefault();
          void updateUsageLimits({
            task_max_tokens: Number(taskMaxTokens),
            monthly_reference_cost_usd: Number(monthlyCost),
          }).then(() => { setMessage("用量上限已更新"); return refresh(); }).catch(() => setMessage("用量上限更新失败"));
        }}>
          <div className="space-y-2"><Label htmlFor="task-max-tokens">单任务 Token 上限</Label><Input id="task-max-tokens" type="number" min={1} max={10000000} value={taskMaxTokens} onChange={(event) => setTaskMaxTokens(event.target.value)} /></div>
          <div className="space-y-2"><Label htmlFor="monthly-cost-cap">本月参考费用上限（USD）</Label><Input id="monthly-cost-cap" type="number" min={0.01} max={10000} step="0.01" value={monthlyCost} onChange={(event) => setMonthlyCost(event.target.value)} /></div>
          <Button type="submit" variant="outline">保存上限</Button>
        </form>
        <p className="mt-2 text-xs text-muted-foreground">这是 EduFlow 内部调用的 Token/参考费用闸门，不限制同一 API Key 在其他应用中的供应商账单。</p>
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
