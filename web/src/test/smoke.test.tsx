import { render, screen } from "@testing-library/react";
import { App } from "@/app/App";

it("renders the EduFlow application", () => {
  render(<App />);
  expect(screen.getByText("EduFlow")).toBeInTheDocument();
});

it("renders an accessible EduFlow brand image", () => {
  render(<App />);
  expect(screen.getByRole("img", { name: "EduFlow" })).toBeInTheDocument();
});
