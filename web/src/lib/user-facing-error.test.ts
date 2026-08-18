import { describe, expect, it } from "vitest";
import { toUserFacingError } from "./user-facing-error";

describe("toUserFacingError", () => {
  it.each([
    ["Error code: 402 Insufficient Balance", "智能生成额度不足"],
    ["401 unauthorized api key", "AI 服务接入未生效"],
    ["429 rate limit", "AI 服务暂时繁忙"],
    ["network timeout", "生成服务暂时无法连接"],
    ["render compile syntax error", "互动内容暂时无法展示"],
  ])("translates %s", (raw, title) => {
    const result = toUserFacingError(raw);
    expect(result.title).toBe(title);
    expect(result.message).not.toContain(raw);
  });
});
