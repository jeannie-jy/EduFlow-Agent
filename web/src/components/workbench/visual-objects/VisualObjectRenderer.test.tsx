import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { ArrayObject } from "./ArrayObject";
import { FormulaObject } from "./FormulaObject";

describe("generic visual object presentation", () => {
  it("renders LaTeX as formatted mathematics instead of raw commands", () => {
    const { container } = render(
      <FormulaObject object={{ id: "goal", type: "formula", latex: String.raw`a[0] \le a[1] \le \cdots \le a[n-1]` }} />,
    );

    const visibleMath = container.querySelector(".katex-html");
    expect(visibleMath).toBeInTheDocument();
    expect(visibleMath?.textContent).toContain("≤");
    expect(visibleMath?.textContent).toContain("⋯");
    expect(visibleMath?.textContent).not.toContain("\\le");
  });

  it("places array indices in a separate row below the values", () => {
    const { container } = render(
      <ArrayObject object={{
        id: "values",
        type: "array",
        label: "示例数据",
        cells: [{ value: 38 }, { value: 27 }, { value: 43 }],
      }} />,
    );

    expect(screen.getByRole("list", { name: "示例数据" })).toHaveClass("flex-col");
    expect(container.querySelector('[aria-label="数组索引"]')).toBeInTheDocument();
    expect(screen.getAllByRole("listitem")).toHaveLength(3);
  });
});
