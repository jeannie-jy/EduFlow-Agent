import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { KnowledgeCardDeck } from "./KnowledgeCardDeck";

const cards = [
  {
    id: "c1",
    title: "最短路径",
    definition: "两个节点之间权重和最小的路径。",
    category: "基础",
    difficulty: 2,
    relatedFrameIds: ["f_001"],
  },
  {
    id: "c2",
    title: "松弛操作",
    definition: "尝试通过中间节点缩短距离。",
    intuition: "找到更短的路就更新记录。",
    category: "核心",
    difficulty: 3,
  },
];

describe("KnowledgeCardDeck", () => {
  it("supports direct card navigation and reading progress", () => {
    render(<KnowledgeCardDeck cards={cards} />);

    fireEvent.click(screen.getByRole("button", { name: "阅读卡片 2：松弛操作" }));
    expect(screen.getByRole("button", { name: "阅读卡片 2：松弛操作" })).toHaveAttribute("aria-pressed", "true");
    expect(screen.getByText("找到更短的路就更新记录。")).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "标记已阅读" }));
    expect(screen.getByRole("button", { name: "已阅读" })).toBeInTheDocument();
    expect(screen.getByText("1 / 2 已阅读")).toBeInTheDocument();
  });

  it("filters by category and jumps to related frames", () => {
    const onFrameClick = vi.fn();
    render(<KnowledgeCardDeck cards={cards} onFrameClick={onFrameClick} />);

    fireEvent.click(screen.getByRole("button", { name: "基础" }));
    expect(screen.getByRole("button", { name: "阅读卡片 1：最短路径" })).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /阅读卡片 2/ })).not.toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "f_001" }));
    expect(onFrameClick).toHaveBeenCalledWith("f_001");
  });
});
