export type LoginValues = {
  email: string;
  password: string;
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

export function simulateAuth(delay = 280): Promise<{ ok: true }> {
  return new Promise((resolve) => {
    window.setTimeout(() => resolve({ ok: true }), delay);
  });
}
