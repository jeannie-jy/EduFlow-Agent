import { render } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { CodeBlockObject } from "./CodeBlockObject";

describe("CodeBlockObject", () => {
  it("highlights numbers without corrupting generated markup", () => {
    render(
      <CodeBlockObject
        object={{
          id: "code",
          type: "code_block",
          language: "python",
          code: "for j in range(n - i - 1):",
          highlight_lines: [1],
        }}
      />,
    );

    expect(document.querySelector("tbody")?.textContent).toContain("for j in range(n - i - 1):");
    expect(document.body.textContent).not.toContain('class="text-info"');
  });
});
