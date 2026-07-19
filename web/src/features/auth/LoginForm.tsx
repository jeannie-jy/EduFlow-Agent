import { Eye, EyeOff, LockKeyhole, Mail } from "lucide-react";
import { useState, type FormEvent } from "react";
import { Link, useNavigate } from "react-router-dom";
import { simulateAuth, validateLogin, type LoginErrors, type LoginValues } from "./auth";

export function LoginForm() {
  const navigate = useNavigate();
  const [values, setValues] = useState<LoginValues>({ email: "", password: "" });
  const [errors, setErrors] = useState<LoginErrors>({});
  const [visible, setVisible] = useState(false);
  const [submitting, setSubmitting] = useState(false);

  const update = (key: keyof LoginValues, value: string) => setValues((current) => ({ ...current, [key]: value }));

  async function submit(event: FormEvent) {
    event.preventDefault();
    const nextErrors = validateLogin(values);
    setErrors(nextErrors);
    if (Object.keys(nextErrors).length) return;
    setSubmitting(true);
    await simulateAuth();
    navigate("/app");
  }

  return (
    <div className="auth-form-wrap">
      <header className="auth-form-heading"><p>继续你的学习流</p><h1>欢迎回来</h1><span>登录后继续探索你的教学推演。</span></header>
      <form className="auth-form" onSubmit={submit} noValidate>
        <div className="form-field"><label htmlFor="login-email">邮箱</label><span className="input-shell"><Mail /><input id="login-email" type="email" value={values.email} onChange={(e) => update("email", e.target.value)} autoComplete="email" aria-invalid={Boolean(errors.email)} aria-describedby={errors.email ? "login-email-error" : undefined} placeholder="name@example.com" /></span>{errors.email && <small id="login-email-error">{errors.email}</small>}</div>
        <div className="form-field"><label htmlFor="login-password">密码</label><span className="input-shell"><LockKeyhole /><input id="login-password" type={visible ? "text" : "password"} value={values.password} onChange={(e) => update("password", e.target.value)} autoComplete="current-password" aria-invalid={Boolean(errors.password)} aria-describedby={errors.password ? "login-password-error" : undefined} placeholder="输入你的密码" /><button type="button" aria-label={visible ? "隐藏密码" : "显示密码"} onClick={() => setVisible((value) => !value)}>{visible ? <EyeOff /> : <Eye />}</button></span>{errors.password && <small id="login-password-error">{errors.password}</small>}</div>
        <div className="form-options"><label><input type="checkbox" /> <span>记住我</span></label><button type="button" className="text-button">忘记密码？</button></div>
        <button className="button auth-submit" type="submit" disabled={submitting}>{submitting ? "正在进入…" : "登录 EduFlow"}</button>
        <p className="auth-switch">还没有账号？ <Link to="/register">创建账号</Link></p>
      </form>
    </div>
  );
}
