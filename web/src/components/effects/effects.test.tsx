import { render, screen } from "@testing-library/react";
import { GenerationBorder } from "./GenerationBorder";
import { WorkspaceGrid } from "./WorkspaceGrid";

it("keeps decorative effects out of the accessibility tree", () => {
  render(<WorkspaceGrid />);
  expect(screen.queryByRole("img")).not.toBeInTheDocument();
  expect(document.querySelector("[aria-hidden='true']")).toBeTruthy();
});

it("renders the static generation border only while planning", () => {
  const { container, rerender } = render(<GenerationBorder generation="idle" />);
  expect(container).toBeEmptyDOMElement();

  rerender(<GenerationBorder generation="planning" />);
  expect(container.querySelector("[aria-hidden='true']")).toHaveClass("pointer-events-none");
  expect(container.querySelector(".motion-reduce\\:hidden")).toBeTruthy();
});
