import { render, screen } from "@testing-library/react";
import { App } from "@/app/App";

it("renders the EduFlow application", () => {
  render(<App />);
  expect(screen.getByText("EduFlow")).toBeInTheDocument();
});
