/**
 * ComparisonView 组件测试。
 */

import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";
import { ComparisonView, type ComparisonData } from "./ComparisonView";

// ============================================================================
// Helpers
// ============================================================================

function makeData(overrides: Partial<ComparisonData> = {}): ComparisonData {
  return {
    topic: "排序算法对比",
    algorithms: [
      {
        name: "Quick Sort",
        description: "Divide and conquer, pick pivot",
        pros: ["Fast average case", "In-place sorting"],
        cons: ["Worst case O(n²)", "Not stable"],
      },
      {
        name: "Merge Sort",
        description: "Divide and merge",
        pros: ["Stable sort", "Guaranteed O(n log n)"],
        cons: ["Requires extra memory", "Not in-place"],
      },
      {
        name: "Bubble Sort",
        description: "Repeatedly swap adjacent elements",
        pros: ["Simple implementation", "Stable"],
        cons: ["Very slow O(n²)", "Not practical"],
      },
    ],
    dimensions: ["时间复杂度", "空间复杂度", "稳定性", "实现难度"],
    comparison_table: [
      { dimension: "时间复杂度", "Quick Sort": "O(n log n) avg", "Merge Sort": "O(n log n)", "Bubble Sort": "O(n²)" },
      { dimension: "空间复杂度", "Quick Sort": "O(log n)", "Merge Sort": "O(n)", "Bubble Sort": "O(1)" },
      { dimension: "稳定性", "Quick Sort": "不稳定", "Merge Sort": "稳定", "Bubble Sort": "稳定" },
      { dimension: "实现难度", "Quick Sort": "中等", "Merge Sort": "中等", "Bubble Sort": "简单" },
    ],
    scenario_analysis: "Quick Sort 适合通用排序场景。需要稳定排序时选 Merge Sort。Bubble Sort 仅用于教学。",
    ...overrides,
  };
}

// ============================================================================
// Tests
// ============================================================================

describe("ComparisonView", () => {
  it("renders topic title", () => {
    render(<ComparisonView data={makeData()} />);
    expect(screen.getByText("排序算法对比")).toBeInTheDocument();
  });

  it("renders algorithm count summary", () => {
    render(<ComparisonView data={makeData()} />);
    expect(screen.getByText(/共对比 3 个算法，4 个维度/)).toBeInTheDocument();
  });

  it("renders all algorithm names", () => {
    render(<ComparisonView data={makeData()} />);
    // Names appear in cards AND table headers, use getAllByText
    expect(screen.getAllByText("Quick Sort").length).toBeGreaterThanOrEqual(1);
    expect(screen.getAllByText("Merge Sort").length).toBeGreaterThanOrEqual(1);
    expect(screen.getAllByText("Bubble Sort").length).toBeGreaterThanOrEqual(1);
  });

  it("renders algorithm descriptions", () => {
    render(<ComparisonView data={makeData()} />);
    expect(screen.getByText("Divide and conquer, pick pivot")).toBeInTheDocument();
    expect(screen.getByText("Divide and merge")).toBeInTheDocument();
  });

  it("renders pros and cons", () => {
    render(<ComparisonView data={makeData()} />);
    expect(screen.getByText("Fast average case")).toBeInTheDocument();
    expect(screen.getByText("Worst case O(n²)")).toBeInTheDocument();
    expect(screen.getByText("Stable sort")).toBeInTheDocument();
    expect(screen.getByText("Requires extra memory")).toBeInTheDocument();
  });

  it("renders comparison table headers", () => {
    render(<ComparisonView data={makeData()} />);
    // Table headers include dimension column + algorithm names
    const tableHeaders = screen.getAllByText("Quick Sort");
    // One in card, one in table header
    expect(tableHeaders.length).toBeGreaterThanOrEqual(2);
  });

  it("renders comparison table data rows", () => {
    render(<ComparisonView data={makeData()} />);
    expect(screen.getByText("O(n log n) avg")).toBeInTheDocument();
    expect(screen.getByText("O(n²)")).toBeInTheDocument();
  });

  it("renders scenario analysis section", () => {
    render(<ComparisonView data={makeData()} />);
    expect(screen.getByText(/选型建议/)).toBeInTheDocument();
    expect(screen.getByText(/Quick Sort 适合通用排序场景/)).toBeInTheDocument();
  });

  it("renders empty state when no algorithms", () => {
    render(<ComparisonView data={makeData({ algorithms: [] })} />);
    expect(screen.getByText("暂无对比数据")).toBeInTheDocument();
  });

  it("renders single algorithm", () => {
    const data = makeData({
      algorithms: [
        { name: "Quick Sort", description: "Fast", pros: ["Fast", "In-place"], cons: ["Unstable"] },
      ],
      comparison_table: [
        { dimension: "速度", "Quick Sort": "快" },
      ],
    });
    render(<ComparisonView data={data} />);
    expect(screen.getAllByText("Quick Sort").length).toBeGreaterThanOrEqual(1);
    // "Fast" appears as description AND as a pro — both valid
    expect(screen.getAllByText("Fast").length).toBeGreaterThanOrEqual(1);
  });

  it("renders pros and cons labels", () => {
    render(<ComparisonView data={makeData()} />);
    // 优点/缺点以 lucide 图标 + aria-label 表达（DESIGN.md：禁止 Emoji/文本符号）
    const prosLabels = screen.getAllByLabelText("优点");
    const consLabels = screen.getAllByLabelText("缺点");
    expect(prosLabels.length).toBe(3);
    expect(consLabels.length).toBe(3);
  });

  it("renders table with correct number of rows", () => {
    render(<ComparisonView data={makeData()} />);
    // 4 dimensions → 4 data rows + 1 header row
    const rows = document.querySelectorAll("tbody tr");
    expect(rows.length).toBe(4);
  });

  it("table row shows dimension name", () => {
    render(<ComparisonView data={makeData()} />);
    expect(screen.getByText("时间复杂度")).toBeInTheDocument();
    expect(screen.getByText("空间复杂度")).toBeInTheDocument();
    expect(screen.getByText("稳定性")).toBeInTheDocument();
    expect(screen.getByText("实现难度")).toBeInTheDocument();
  });

  it("handles comparison data with extra table columns", () => {
    const data = makeData({
      comparison_table: [
        { dimension: "速度", "Quick Sort": "快", "Merge Sort": "中", "Bubble Sort": "慢", "Extra": "ignored" },
      ],
    });
    render(<ComparisonView data={data} />);
    expect(screen.getByText("快")).toBeInTheDocument();
  });

  it("handles missing algorithm data in table with dash", () => {
    const data = makeData({
      algorithms: [
        { name: "Quick Sort", description: "Fast", pros: ["Fast"], cons: ["Unstable"] },
        { name: "Merge Sort", description: "Stable", pros: ["Stable"], cons: ["Memory"] },
      ],
      comparison_table: [
        { dimension: "速度", "Quick Sort": "快" },  // Missing Merge Sort
      ],
    });
    render(<ComparisonView data={data} />);
    // Missing value should show "—"
    const dashes = screen.getAllByText("—");
    expect(dashes.length).toBeGreaterThanOrEqual(1);
  });
});
