/**
 * CodeSandbox 组件测试。
 */

import { describe, expect, it } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { CodeSandbox, type SandboxData } from "./CodeSandbox";

function makeData(overrides: Partial<SandboxData> = {}): SandboxData {
  return {
    language: "python",
    starter_code: "def sort(arr):\n    # TODO: implement\n    pass",
    full_solution: "def sort(arr):\n    return sorted(arr)",
    test_cases: [
      { name: "基本测试", input: { arr: [3, 1, 2] }, expected_output: { sorted: [1, 2, 3] }, description: "正常数组" },
      { name: "空数组", input: { arr: [] }, expected_output: { sorted: [] } },
    ],
    editable_params: [
      { key: "size", label: "数组大小", type: "number", default: 10, description: "输入规模" },
    ],
    learning_notes: "冒泡排序是最基础的排序算法。",
    time_complexity: "O(n²)",
    space_complexity: "O(1)",
    ...overrides,
  };
}

describe("CodeSandbox", () => {
  it("renders empty state when no code", () => {
    render(<CodeSandbox data={makeData({ starter_code: "", full_solution: "" })} />);
    expect(screen.getByText("暂无代码数据")).toBeInTheDocument();
  });

  it("renders language label", () => {
    render(<CodeSandbox data={makeData()} />);
    expect(screen.getByText("Python 代码")).toBeInTheDocument();
  });

  it("renders starter code", () => {
    render(<CodeSandbox data={makeData()} />);
    expect(screen.getByText(/def sort/)).toBeInTheDocument();
  });

  it("renders complexity badges", () => {
    render(<CodeSandbox data={makeData()} />);
    expect(screen.getByText(/O\(n²\)/)).toBeInTheDocument();
    expect(screen.getByText(/O\(1\)/)).toBeInTheDocument();
  });

  it("toggles solution visibility", () => {
    render(<CodeSandbox data={makeData()} />);
    // Solution should initially be hidden (full_solution contains "sorted(arr)")
    expect(screen.queryByText(/sorted\(arr\)/)).toBeNull();
    // Click "查看完整解答" button
    const toggleBtn = screen.getByText(/查看完整解答/);
    fireEvent.click(toggleBtn);
    expect(screen.getByText(/sorted\(arr\)/)).toBeInTheDocument();
    // Should now show "隐藏完整解答"
    expect(screen.getByText(/隐藏完整解答/)).toBeInTheDocument();
  });

  it("renders test cases", () => {
    render(<CodeSandbox data={makeData()} />);
    expect(screen.getByText("基本测试")).toBeInTheDocument();
    expect(screen.getByText("空数组")).toBeInTheDocument();
    expect(screen.getByText(/测试用例 \(2\)/)).toBeInTheDocument();
  });

  it("renders test case details", () => {
    render(<CodeSandbox data={makeData()} />);
    expect(screen.getByText("正常数组")).toBeInTheDocument();
    expect(screen.getByText(/"arr":\[3,1,2\]/)).toBeInTheDocument();
  });

  it("renders editable params", () => {
    render(<CodeSandbox data={makeData()} />);
    expect(screen.getByText(/可调参数/)).toBeInTheDocument();
    expect(screen.getByText(/数组大小: 10/)).toBeInTheDocument();
  });

  it("renders learning notes", () => {
    render(<CodeSandbox data={makeData()} />);
    expect(screen.getByText(/学习笔记/)).toBeInTheDocument();
    expect(screen.getByText("冒泡排序是最基础的排序算法。")).toBeInTheDocument();
  });

  it("hide complexity badges when not provided", () => {
    render(<CodeSandbox data={makeData({ time_complexity: undefined, space_complexity: undefined })} />);
    expect(screen.queryByText(/O\(/)).toBeNull();
  });
});
