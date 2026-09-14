import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { AuthShell } from "./AuthShell";
import { login, validateLogin, type LoginErrors } from "./auth";
import { setAuthState } from "@/lib/auth";
import { Eye, EyeOff } from "lucide-react";

export function LoginPage() {
  const navigate = useNavigate();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [totpCode, setTotpCode] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [errors, setErrors] = useState<LoginErrors>({});
  const [submitting, setSubmitting] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    const validation = validateLogin({ email, password });
    setErrors(validation);
    if (Object.keys(validation).length > 0) return;

    setSubmitting(true);
    try {
      const user = await login({ email, password, totp_code: totpCode || undefined });
      setAuthState({ id: user.id, isAuthenticated: true, nickname: user.nickname, email: user.email, role: user.role });
      navigate(user.email_verified ? "/app" : "/verify-email");
    } catch {
      setErrors({ password: "邮箱或密码错误，请重试" });
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <AuthShell>
      <h1 className="text-2xl font-bold text-slate-900 mb-2">欢迎回来</h1>
      <p className="text-sm text-slate-500 mb-8">登录你的 EduFlow 账号继续学习</p>

      <form onSubmit={handleSubmit} className="space-y-5">
        <div className="space-y-2">
          <Label htmlFor="email">邮箱</Label>
          <Input
            id="email"
            type="email"
            autoComplete="email"
            placeholder="you@example.com"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
          />
          {errors.email && <p className="text-xs text-red-500">{errors.email}</p>}
        </div>

        <div className="space-y-2">
          <Label htmlFor="totp-code">管理员验证码（如已启用 MFA）</Label>
          <Input id="totp-code" inputMode="numeric" autoComplete="one-time-code" placeholder="6 位验证码" value={totpCode} onChange={(e) => setTotpCode(e.target.value)} />
        </div>

        <div className="space-y-2">
          <Label htmlFor="password">密码</Label>
          <div className="relative">
            <Input
              id="password"
              type={showPassword ? "text" : "password"}
              autoComplete="current-password"
              placeholder="输入密码"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
            />
            <button
              type="button"
              className="absolute right-3 top-1/2 -translate-y-1/2 text-slate-400 hover:text-slate-600"
              onClick={() => setShowPassword(!showPassword)}
              aria-label={showPassword ? "隐藏密码" : "显示密码"}
            >
              {showPassword ? <EyeOff size={18} /> : <Eye size={18} />}
            </button>
          </div>
          {errors.password && <p className="text-xs text-red-500">{errors.password}</p>}
        </div>

        <Button type="submit" className="w-full" disabled={submitting}>
          {submitting ? "正在进入…" : "登录 EduFlow"}
        </Button>
        <p className="text-right text-sm"><Link to="/forgot-password" className="text-indigo-600">忘记密码？</Link></p>
      </form>

      <p className="mt-6 text-center text-sm text-slate-500">
        还没有账号？{" "}
        <Link to="/register" className="font-medium text-indigo-600 hover:text-indigo-500">
          创建账号
        </Link>
      </p>
    </AuthShell>
  );
}
