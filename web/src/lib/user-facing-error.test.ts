import { describe, expect, it } from "vitest";
import { toUserFacingError } from "./user-facing-error";

describe("toUserFacingError", () => {
  it.each([
    ["Error code: 402 Insufficient Balance", "智能生成额度不足"],
    ["401 unauthorized api key", "AI 服务接入未生效"],
    ["429 rate limit", "AI 服务暂时繁忙"],
    ["network timeout", "生成服务暂时无法连接"],
    ["Project has no frames to export", "缺少推演脚本"],
    ["缺少推演脚本（frames），已自动补充", "缺少推演脚本"],
    ["render compile syntax error", "互动内容暂时无法展示"],
  ])("translates %s", (raw, title) => {
    const result = toUserFacingError(raw);
    expect(result.title).toBe(title);
    expect(result.message).not.toContain(raw);
  });

  it.each([
    ["Video export is disabled because an isolated render worker is not configured", "视频制作服务未启动"],
    ["render compile syntax error", "视频渲染未完成"],
  ])("uses video-specific guidance for %s", (raw, title) => {
    const result = toUserFacingError(raw, "video");
    expect(result.title).toBe(title);
    expect(result.message).not.toContain(raw);
  });
});
