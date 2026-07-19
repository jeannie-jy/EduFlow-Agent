import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { vi } from "vitest";
import { renderWithProviders } from "@/test/render";
import { WorkbenchPage } from "./WorkbenchPage";

it("composes Base UI triggers without React ref warnings", () => {
  const consoleError = vi.spyOn(console, "error").mockImplementation(() => undefined);

  try {
    renderWithProviders(<WorkbenchPage />);
    const messages = consoleError.mock.calls.flat().join(" ");
    expect(messages).not.toContain("Function components cannot be given refs");
  } finally {
    consoleError.mockRestore();
  }
});

it("turns a teaching brief into an observable mock plan", async () => {
  renderWithProviders(<WorkbenchPage />);
  const brief = screen.getByRole("textbox", { name: "教学简报" });
  await userEvent.clear(brief);
  await userEvent.type(brief, "用 Dijkstra 演示校园最短路径");
  await userEvent.click(screen.getByRole("button", { name: "生成推演计划" }));
  expect(screen.getByRole("status")).toHaveTextContent("正在生成推演计划");
  expect(screen.getByText("识别知识结构")).toBeVisible();
});
