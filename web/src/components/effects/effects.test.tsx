import { render, screen } from "@testing-library/react";
import { afterEach, beforeEach, vi } from "vitest";
import { GenerationBorder } from "./GenerationBorder";
import { WorkspaceGrid } from "./WorkspaceGrid";

const defaultMatchMedia = window.matchMedia;

it("keeps decorative effects out of the accessibility tree", () => {
  render(<WorkspaceGrid />);
  expect(screen.queryByRole("img")).not.toBeInTheDocument();
  expect(document.querySelector("[aria-hidden='true']")).toBeTruthy();
});

it("renders the static generation border only while planning", () => {
  const { container, rerender } = render(<GenerationBorder generation="idle" />);
  expect(container).toBeEmptyDOMElement();

  rerender(<GenerationBorder generation="planning" />);
  const border = container.querySelector("[aria-hidden='true']");
  expect(border).toHaveClass("pointer-events-none");
  expect(border?.firstElementChild).toBeTruthy();
  expect(container.querySelector(".motion-reduce\\:hidden")).not.toBeInTheDocument();
});

describe("reduced motion", () => {
  beforeEach(() => {
    window.matchMedia = vi.fn().mockReturnValue({ matches: true }) as typeof window.matchMedia;
    vi.stubGlobal(
      "ResizeObserver",
      class {
        observe() {}
        disconnect() {}
      },
    );
  });

  afterEach(() => {
    window.matchMedia = defaultMatchMedia;
    vi.unstubAllGlobals();
  });

  it("keeps the workspace grid static, hidden, and pointer-inert", () => {
    const { container } = render(<WorkspaceGrid />);
    const grid = container.firstElementChild;

    expect(grid).toHaveAttribute("aria-hidden", "true");
    expect(grid).toHaveClass("pointer-events-none");
    expect(grid?.querySelectorAll("svg")).toHaveLength(1);
  });

  it("keeps the planning border static, hidden, and pointer-inert", () => {
    const { container } = render(<GenerationBorder generation="planning" />);
    const border = container.firstElementChild;

    expect(border).toHaveAttribute("aria-hidden", "true");
    expect(border).toHaveClass("pointer-events-none");
    expect(border?.firstElementChild).toBeTruthy();
    expect(border?.children).toHaveLength(1);
  });
});
