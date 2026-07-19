import { screen } from "@testing-library/react";
import { App } from "@/app/App";
import { renderWithProviders } from "@/test/render";

it("renders the EduFlow application", () => {
  renderWithProviders(<App />);
  expect(screen.getByRole("navigation", { name: "主导航" })).toBeInTheDocument();
});

it("renders an accessible EduFlow brand link", () => {
  renderWithProviders(<App />);
  expect(screen.getByRole("link", { name: "EduFlow 工作台" })).toBeInTheDocument();
});
