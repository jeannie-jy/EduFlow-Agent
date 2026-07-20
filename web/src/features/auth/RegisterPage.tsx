import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { AuthShell } from "./AuthShell";
import { validateRegistration, simulateAuth, type RegistrationErrors } from "./auth";
import { setAuthState } from "@/lib/auth";
import { Eye, EyeOff } from "lucide-react";

export function RegisterPage() {
  const navigate = useNavigate();
  const [nickname, setNickname] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [confirmation, setConfirmation] = useState("");
  const [acceptedTerms, setAcceptedTerms] = useState(false);
  const [showPassword, setShowPassword] = useState(false);
  const [errors, setErrors] = useState<RegistrationErrors>({});
  const [submitting, setSubmitting] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    const validation = validateRegistration({
      nickname,
      email,
      password,
      confirmation,
      acceptedTerms,
    });
    setErrors(validation);
    if (Object.keys(validation).length > 0) return;

    setSubmitting(true);
    await simulateAuth();
    setAuthState({ isAuthenticated: true, nickname, email });
    setSubmitting(false);
    navigate("/app");
  };

  return (
    <AuthShell>
      <h1 className="text-2xl font-bold text-slate-900 mb-2">创建你的学习空间</h1>
      <p className="text-sm text-slate-500 mb-8">注册 EduFlow，开始交互式学习体验</p>

      <form onSubmit={handleSubmit} className="space-y-5">
        <div className="space-y-2">
          <Label htmlFor="nickname">昵称</Label>
          <Input
            id="nickname"
            type="text"
            autoComplete="name"
            placeholder="你的昵称"
            value={nickname}
            onChange={(e) => setNickname(e.target.value)}
          />
          {errors.nickname && <p className="text-xs text-red-500">{errors.nickname}</p>}
        </div>

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
          <Label htmlFor="password">密码</Label>
          <div className="relative">
            <Input
              id="password"
              type={showPassword ? "text" : "password"}
              autoComplete="new-password"
              placeholder="至少 8 位，包含字母和数字"
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

        <div className="space-y-2">
          <Label htmlFor="confirmation">确认密码</Label>
          <Input
            id="confirmation"
            type="password"
            autoComplete="new-password"
            placeholder="再次输入密码"
            value={confirmation}
            onChange={(e) => setConfirmation(e.target.value)}
          />
          {errors.confirmation && <p className="text-xs text-red-500">{errors.confirmation}</p>}
        </div>

        <div className="flex items-start gap-3">
          <input
            id="terms"
            type="checkbox"
            className="mt-1 size-4 rounded border-slate-300 text-indigo-600 focus:ring-indigo-500"
            checked={acceptedTerms}
            onChange={(e) => setAcceptedTerms(e.target.checked)}
          />
          <Label htmlFor="terms" className="text-sm text-slate-500 cursor-pointer">
            我已阅读并同意 EduFlow 服务条款和隐私政策
          </Label>
        </div>
        {errors.acceptedTerms && <p className="text-xs text-red-500">{errors.acceptedTerms}</p>}

        <Button type="submit" className="w-full" disabled={submitting}>
          {submitting ? "正在创建…" : "创建免费账号"}
        </Button>
      </form>

      <p className="mt-6 text-center text-sm text-slate-500">
        已有账号？{" "}
        <Link to="/login" className="font-medium text-indigo-600 hover:text-indigo-500">
          立即登录
        </Link>
      </p>
    </AuthShell>
  );
}