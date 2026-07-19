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

it("keeps workbench effects decorative while planning", async () => {
  renderWithProviders(<WorkbenchPage />);

  await userEvent.click(screen.getByRole("button", { name: "生成推演计划" }));

  expect(document.querySelector("main > [aria-hidden='true']")).toBeTruthy();
  expect(screen.getByRole("status").querySelector("[aria-hidden='true']")).toBeTruthy();
});

it("shows a mathematically consistent Dijkstra relaxation state", () => {
  renderWithProviders(<WorkbenchPage />);

  expect(screen.getByRole("row", { name: "C 3 B 当前节点" })).toBeVisible();
  expect(screen.getByRole("row", { name: "D 6 C 未访问" })).toBeVisible();
  expect(screen.getByRole("row", { name: "E 6 C 未访问" })).toBeVisible();
  expect(screen.getByRole("row", { name: "F 4 B 未访问" })).toBeVisible();
  expect(screen.getByText(/本步将 D 与 E 的距离更新为 6/)).toBeVisible();
});

it("names every graph node state and edge endpoint for assistive technology", () => {
  renderWithProviders(<WorkbenchPage />);

  expect(
    screen.getByRole("listitem", { name: "节点 C，当前节点，距离 3" }),
  ).toBeVisible();
  expect(
    screen.getByRole("listitem", { name: "节点 B，已确定，距离 2" }),
  ).toBeVisible();
  expect(
    screen.getByRole("listitem", { name: "节点 F，未访问，距离 4" }),
  ).toBeVisible();
  expect(
    screen.getByRole("listitem", { name: "边 A 到 B，权重 2" }),
  ).toBeVisible();
  expect(
    screen.getByRole("listitem", { name: "边 B 到 F，权重 2" }),
  ).toBeVisible();
});

it("programmatically labels the operable duration slider", () => {
  renderWithProviders(<WorkbenchPage />);

  expect(screen.getByRole("slider", { name: "课堂时长" })).toBeVisible();
});

it("keeps collapsed-region controls discoverable at every breakpoint", () => {
  renderWithProviders(<WorkbenchPage />);

  expect(screen.getByRole("button", { name: "简报与约束" })).not.toHaveClass(
    "hidden",
  );
  expect(screen.getByRole("button", { name: "推演序列 · 4 步" })).not.toHaveClass(
    "hidden",
  );
});

it("uses zero-minimum desktop columns to prevent shell overflow", () => {
  renderWithProviders(<WorkbenchPage />);

  expect(screen.getByTestId("workbench-regions")).toHaveClass(
    "xl:grid-cols-[minmax(0,0.8fr)_minmax(0,0.9fr)_minmax(0,1.55fr)]",
  );
});

it("keeps the desktop AI status inside the viewport workspace", () => {
  renderWithProviders(<WorkbenchPage />);

  expect(screen.getByTestId("workbench-page")).toHaveClass(
    "xl:h-[calc(100svh-6.5rem)]",
    "xl:overflow-hidden",
  );
  expect(screen.getByTestId("workbench-regions")).toHaveClass("xl:overflow-hidden");
  expect(screen.getByRole("status")).toHaveClass("shrink-0");
});
