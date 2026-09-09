/**
 * MisconceptionGallery 组件测试。
 */

import { describe, expect, it } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { MisconceptionGallery, type MisconceptionItem } from "./MisconceptionGallery";

function makeItems(n = 2): MisconceptionItem[] {
  return Array.from({ length: n }, (_, i) => ({
    id: `m${i + 1}`,
    concept: `Concept ${i + 1}`,
    misconception: `Wrong idea ${i + 1}`,
    correction: `Right idea ${i + 1} with enough detail`,
    counter_example: i === 0 ? `Counter ${i + 1}` : undefined,
    why_it_matters: i === 0 ? `Why important ${i + 1}` : undefined,
    difficulty: (i % 3) + 1 as 1 | 2 | 3,
  }));
}

describe("MisconceptionGallery", () => {
  it("renders empty state", () => {
    render(<MisconceptionGallery items={[]} />);
    expect(screen.getByText("暂无误区数据")).toBeInTheDocument();
  });

  it("renders all misconception cards", () => {
    render(<MisconceptionGallery items={makeItems(3)} />);
    expect(screen.getByText("Concept 1")).toBeInTheDocument();
    expect(screen.getByText("Concept 2")).toBeInTheDocument();
    expect(screen.getByText("Concept 3")).toBeInTheDocument();
  });

  it("shows item count", () => {
    render(<MisconceptionGallery items={makeItems(2)} />);
    expect(screen.getByText(/2 个常见误解/)).toBeInTheDocument();
  });

  it("shows wrong idea (strikethrough)", () => {
    render(<MisconceptionGallery items={makeItems(1)} />);
    expect(screen.getByText(/Wrong idea 1/)).toBeInTheDocument();
  });

  it("expands to show correction on click", () => {
    render(<MisconceptionGallery items={makeItems(1)} />);
    // Click the card header to expand
    fireEvent.click(screen.getByText("Concept 1").closest("button")!);
    expect(screen.getByText(/Right idea 1 with enough detail/)).toBeInTheDocument();
  });

  it("shows counter example when expanded", () => {
    render(<MisconceptionGallery items={makeItems(1)} />);
    fireEvent.click(screen.getByText("Concept 1").closest("button")!);
    expect(screen.getByText("Counter 1")).toBeInTheDocument();
  });

  it("shows why_it_matters when expanded", () => {
    render(<MisconceptionGallery items={makeItems(1)} />);
    fireEvent.click(screen.getByText("Concept 1").closest("button")!);
    expect(screen.getByText("Why important 1")).toBeInTheDocument();
  });

  it("does not show counter_example for item without it", () => {
    render(<MisconceptionGallery items={makeItems(2)} />);
    // Expand the second item (which has no counter_example)
    fireEvent.click(screen.getByText("Concept 2").closest("button")!);
    expect(screen.getByText(/Right idea 2 with enough detail/)).toBeInTheDocument();
    // "Counter 2" should not exist
    expect(screen.queryByText("Counter 2")).toBeNull();
  });

  it("shows difficulty badge", () => {
    render(<MisconceptionGallery items={makeItems(1)} />);
    expect(screen.getByText("初级")).toBeInTheDocument();
  });

  it("toggles collapse on second click", () => {
    render(<MisconceptionGallery items={makeItems(1)} />);
    const btn = screen.getByText("Concept 1").closest("button")!;
    fireEvent.click(btn);
    expect(screen.getByText(/正确理解/)).toBeInTheDocument();
    fireEvent.click(btn);
    // After collapsing, correction text should not be visible
    expect(screen.queryByText(/Right idea 1 with enough detail/)).toBeNull();
  });

  it("renders correct structure labels in expanded view", () => {
    render(<MisconceptionGallery items={makeItems(1)} />);
    fireEvent.click(screen.getByText("Concept 1").closest("button")!);
    expect(screen.getByText(/正确理解/)).toBeInTheDocument();
    expect(screen.getByText(/反例说明/)).toBeInTheDocument();
    expect(screen.getByText(/为什么重要/)).toBeInTheDocument();
  });
});
