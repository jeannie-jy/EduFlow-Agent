import { describe, expect, it } from "vitest";
import { ApiError, NetworkError, TimeoutError } from "@/services/api-client";
import { getRegistrationErrorMessage } from "./auth";

function apiError(status: number, message: string) {
  return new ApiError(status, {
    error: { code: "TEST_ERROR", message },
  });
}

describe("getRegistrationErrorMessage", () => {
  it("explains an existing email", () => {
    expect(getRegistrationErrorMessage(apiError(409, "Email already registered"))).toBe(
      "该邮箱已注册，请直接登录或找回密码",
    );
  });

  it("explains rate limits and disabled registration", () => {
    expect(getRegistrationErrorMessage(apiError(429, "Too many registration attempts"))).toBe(
      "注册尝试过于频繁，请稍后再试",
    );
    expect(getRegistrationErrorMessage(apiError(403, "Registration is disabled"))).toBe(
      "当前暂未开放新用户注册",
    );
  });

  it("distinguishes challenge, policy, and password validation", () => {
    expect(getRegistrationErrorMessage(apiError(422, "Expired registration challenge"))).toBe(
      "注册验证已失效，请刷新页面后重试",
    );
    expect(getRegistrationErrorMessage(apiError(422, "Please accept the latest service terms and privacy policy"))).toBe(
      "服务条款或隐私政策已更新，请刷新页面后重新确认",
    );
    expect(getRegistrationErrorMessage(apiError(422, "Password must contain letters and numbers"))).toBe(
      "密码需至少 8 位，并同时包含字母和数字",
    );
  });

  it("explains connectivity, timeout, and server failures", () => {
    expect(getRegistrationErrorMessage(new NetworkError("Failed to fetch"))).toBe(
      "无法连接到服务器，请检查网络或确认后端已启动",
    );
    expect(getRegistrationErrorMessage(new TimeoutError(30_000))).toBe(
      "注册请求超时，请稍后重试",
    );
    expect(getRegistrationErrorMessage(apiError(503, "Service unavailable"))).toBe(
      "注册服务暂时不可用，请稍后重试",
    );
  });
});
