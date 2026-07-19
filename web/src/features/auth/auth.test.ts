import { validateLogin, validateRegistration } from "./auth";

describe("validateLogin", () => {
  it("requires email and password", () => {
    expect(validateLogin({ email: "", password: "" })).toEqual({
      email: "请输入邮箱地址",
      password: "请输入密码",
    });
  });

  it("rejects an invalid email", () => {
    expect(validateLogin({ email: "invalid", password: "password1" }).email).toBe(
      "请输入有效的邮箱地址",
    );
  });
});

describe("validateRegistration", () => {
  it("requires every registration field and accepted terms", () => {
    expect(
      validateRegistration({
        nickname: "",
        email: "",
        password: "",
        confirmation: "",
        acceptedTerms: false,
      }),
    ).toEqual({
      nickname: "请输入昵称",
      email: "请输入邮箱地址",
      password: "请输入密码",
      confirmation: "请再次输入密码",
      acceptedTerms: "请阅读并同意服务条款",
    });
  });

  it("requires a letter-and-number password of at least eight characters", () => {
    expect(
      validateRegistration({
        nickname: "学习者",
        email: "learner@example.com",
        password: "abcdefgh",
        confirmation: "abcdefgh",
        acceptedTerms: true,
      }).password,
    ).toBe("密码需至少 8 位，并同时包含字母和数字");
  });

  it("requires matching passwords", () => {
    expect(
      validateRegistration({
        nickname: "学习者",
        email: "learner@example.com",
        password: "password1",
        confirmation: "password2",
        acceptedTerms: true,
      }).confirmation,
    ).toBe("两次输入的密码不一致");
  });
});
