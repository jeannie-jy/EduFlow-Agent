import { describe, expect, it } from "vitest";
import { inferExperienceKind } from "./InteractiveExperience";

describe("inferExperienceKind", () => {
  it.each([
    ["社交网络中的信息传播", "", "network"],
    ["二叉树的层级关系", "", "hierarchy"],
    ["自定义通信协议的四阶段交互", "", "sequence"],
    ["用户定义的数组重排方法", "", "collection"],
    ["订单生命周期与状态转移", "", "state"],
    ["函数递归调用", "", "code"],
    ["供需弹性的直观理解", "", "concept"],
  ])("maps %s to a semantic presentation", (topic, code, expected) => {
    expect(inferExperienceKind(topic, code)).toBe(expected);
  });

  it("can infer the presentation from generated content for an unknown topic", () => {
    expect(inferExperienceKind("我的自定义知识", "const nodes = []; const edges = [];")).toBe("network");
  });
});
