import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { AuthShell } from "./AuthShell";
import { forgotPassword, requestEmailVerification, resetPassword, verifyEmail } from "./auth";

function fragmentToken() {
  return new URLSearchParams(window.location.hash.replace(/^#/, "")).get("token") ?? "";
}

export function VerifyEmailPage() {
  const navigate = useNavigate();
  const [message, setMessage] = useState(fragmentToken() ? "点击下方按钮完成验证" : "验证邮件已发送，请检查邮箱");
  const token = fragmentToken();
  return <AuthShell><h1 className="mb-3 text-2xl font-bold">验证邮箱</h1><p className="mb-6 text-sm text-slate-500">{message}</p>
    {token ? <Button className="w-full" onClick={() => void verifyEmail(token).then(() => { window.history.replaceState(null, "", "/verify-email"); navigate("/app"); }).catch(() => setMessage("链接无效或已经过期"))}>完成验证</Button>
      : <Button className="w-full" onClick={() => void requestEmailVerification().then(() => setMessage("新的验证邮件已发送"))}>重新发送</Button>}
  </AuthShell>;
}

export function ForgotPasswordPage() {
  const [email, setEmail] = useState("");
  const [sent, setSent] = useState(false);
  return <AuthShell><h1 className="mb-3 text-2xl font-bold">找回密码</h1>{sent ? <p className="text-sm text-slate-500">如果该邮箱已注册，重置邮件已经发送。</p> : <form className="space-y-4" onSubmit={(event) => { event.preventDefault(); void forgotPassword(email).then(() => setSent(true)); }}>
    <div className="space-y-2"><Label htmlFor="recovery-email">邮箱</Label><Input id="recovery-email" type="email" autoComplete="email" value={email} onChange={(e) => setEmail(e.target.value)} required /></div><Button className="w-full">发送重置邮件</Button>
  </form>}<p className="mt-6 text-center text-sm"><Link to="/login" className="text-indigo-600">返回登录</Link></p></AuthShell>;
}

export function ResetPasswordPage() {
  const navigate = useNavigate();
  const [password, setPassword] = useState("");
  const [message, setMessage] = useState("");
  const token = fragmentToken();
  return <AuthShell><h1 className="mb-3 text-2xl font-bold">设置新密码</h1><form className="space-y-4" onSubmit={(event) => { event.preventDefault(); void resetPassword(token, password).then(() => { window.history.replaceState(null, "", "/reset-password"); navigate("/login"); }).catch(() => setMessage("链接无效、已过期，或密码不符合要求")); }}>
    <div className="space-y-2"><Label htmlFor="new-password">新密码</Label><Input id="new-password" type="password" autoComplete="new-password" value={password} onChange={(e) => setPassword(e.target.value)} minLength={8} required /></div><Button className="w-full" disabled={!token}>重置密码</Button>{message ? <p className="text-sm text-red-500">{message}</p> : null}
  </form></AuthShell>;
}
