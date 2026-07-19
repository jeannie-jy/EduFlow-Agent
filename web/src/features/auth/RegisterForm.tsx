import { Eye, EyeOff, LockKeyhole, Mail, UserRound } from "lucide-react";
import { useState, type FormEvent } from "react";
import { Link, useNavigate } from "react-router-dom";
import { simulateAuth, validateRegistration, type RegistrationErrors, type RegistrationValues } from "./auth";

export function RegisterForm() {
  const navigate = useNavigate();
  const [values, setValues] = useState<RegistrationValues>({ nickname: "", email: "", password: "", confirmation: "", acceptedTerms: false });
  const [errors, setErrors] = useState<RegistrationErrors>({});
  const [visible, setVisible] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const update = <K extends keyof RegistrationValues>(key: K, value: RegistrationValues[K]) => setValues((current) => ({ ...current, [key]: value }));

  async function submit(event: FormEvent) {
    event.preventDefault();
    const nextErrors = validateRegistration(values);
    setErrors(nextErrors);
    if (Object.keys(nextErrors).length) return;
    setSubmitting(true);
    await simulateAuth();
    navigate("/app");
  }

  return (
    <div className="auth-form-wrap auth-form-wrap--register">
      <header className="auth-form-heading"><p>开始一段新的学习流</p><h1>创建你的学习空间</h1><span>免费体验从问题到交互式推演的完整过程。</span></header>
      <form className="auth-form auth-form--register" onSubmit={submit} noValidate>
        <label className="form-field" htmlFor="register-nickname"><span>昵称</span><span className="input-shell"><UserRound /><input id="register-nickname" value={values.nickname} onChange={(e) => update("nickname", e.target.value)} autoComplete="nickname" aria-invalid={Boolean(errors.nickname)} placeholder="怎么称呼你" /></span>{errors.nickname && <small>{errors.nickname}</small>}</label>
        <label className="form-field" htmlFor="register-email"><span>邮箱</span><span className="input-shell"><Mail /><input id="register-email" type="email" value={values.email} onChange={(e) => update("email", e.target.value)} autoComplete="email" aria-invalid={Boolean(errors.email)} placeholder="name@example.com" /></span>{errors.email && <small>{errors.email}</small>}</label>
        <div className="form-row">
          <label className="form-field" htmlFor="register-password"><span>密码</span><span className="input-shell"><LockKeyhole /><input id="register-password" type={visible ? "text" : "password"} value={values.password} onChange={(e) => update("password", e.target.value)} autoComplete="new-password" aria-invalid={Boolean(errors.password)} placeholder="至少 8 位" /><button type="button" aria-label={visible ? "隐藏密码" : "显示密码"} onClick={() => setVisible((value) => !value)}>{visible ? <EyeOff /> : <Eye />}</button></span>{errors.password && <small>{errors.password}</small>}</label>
          <label className="form-field" htmlFor="register-confirmation"><span>确认密码</span><span className="input-shell"><LockKeyhole /><input id="register-confirmation" type={visible ? "text" : "password"} value={values.confirmation} onChange={(e) => update("confirmation", e.target.value)} autoComplete="new-password" aria-invalid={Boolean(errors.confirmation)} placeholder="再次输入" /></span>{errors.confirmation && <small>{errors.confirmation}</small>}</label>
        </div>
        <label className="terms-field"><input type="checkbox" checked={values.acceptedTerms} onChange={(e) => update("acceptedTerms", e.target.checked)} /><span>我已阅读并同意 <button type="button" className="text-button">服务条款</button> 与 <button type="button" className="text-button">隐私政策</button></span></label>
        {errors.acceptedTerms && <small className="terms-error">{errors.acceptedTerms}</small>}
        <button className="button auth-submit" type="submit" disabled={submitting}>{submitting ? "正在创建…" : "创建免费账号"}</button>
        <p className="auth-switch">已有账号？ <Link to="/login">直接登录</Link></p>
      </form>
    </div>
  );
}
