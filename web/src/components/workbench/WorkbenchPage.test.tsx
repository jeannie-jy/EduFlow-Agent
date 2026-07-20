import { act, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { vi } from "vitest";
import { renderWithProviders } from "@/test/render";
import { WorkbenchPage } from "./WorkbenchPage";

it("renders the focused simulation workspace without React ref warnings", () => {
  const consoleError = vi.spyOn(console, "error").mockImplementation(() => undefined);
  try {
    renderWithProviders(<WorkbenchPage />);
    expect(screen.getByRole("heading", { name: "互动推演" })).toBeVisible();
    expect(consoleError.mock.calls.flat().join(" ")).not.toContain("Function components cannot be given refs");
  } finally {
    consoleError.mockRestore();
  }
});

it("shows observable generation status when regeneration starts", () => {
  renderWithProviders(<WorkbenchPage />);
  act(() => window.dispatchEvent(new Event("eduflow:regenerate")));
  expect(screen.getByRole("status")).toHaveTextContent("正在生成第 3 帧");
  expect(screen.getByText("松弛邻接边")).toBeVisible();
});

it("keeps the generation effect decorative while planning", () => {
  renderWithProviders(<WorkbenchPage />);
  act(() => window.dispatchEvent(new Event("eduflow:regenerate")));
  expect(screen.getByTestId("workbench-regions").querySelector("[aria-hidden='true']")).toBeTruthy();
});

it("shows a mathematically consistent Dijkstra relaxation state", () => {
  renderWithProviders(<WorkbenchPage />);
  expect(screen.getByRole("row", { name: "C 3 A 当前节点" })).toBeVisible();
  expect(screen.getByRole("row", { name: "D 9 B 未访问" })).toBeVisible();
  expect(screen.getByRole("row", { name: "E 5 A 未访问" })).toBeVisible();
  expect(screen.getByRole("row", { name: "F 7 C 未访问" })).toBeVisible();
  expect(screen.getAllByText(/F 更新为 7/).length).toBeGreaterThan(0);
});

it("names graph nodes and edge endpoints for assistive technology", () => {
  renderWithProviders(<WorkbenchPage />);
  expect(screen.getByLabelText("节点 C，当前节点，距离 3")).toBeInTheDocument();
  expect(screen.getByLabelText("节点 B，已确定，距离 2")).toBeInTheDocument();
  expect(screen.getByLabelText("节点 F，未访问，距离 7")).toBeInTheDocument();
  expect(screen.getByRole("listitem", { name: "边 A 到 B，权重 2" })).toBeInTheDocument();
});

it("changes frames through playback controls and timeline", async () => {
  renderWithProviders(<WorkbenchPage />);
  await userEvent.click(screen.getByRole("button", { name: "下一帧" }));
  expect(screen.getByText("步骤 9 / 14")).toBeVisible();
  await userEvent.click(screen.getByRole("button", { name: "跳到第 8 帧" }));
  expect(screen.getByText("步骤 8 / 14")).toBeVisible();
});

it("keeps all inspector modes keyboard discoverable", () => {
  renderWithProviders(<WorkbenchPage />);
  expect(screen.getByRole("tab", { name: "讲解" })).toBeVisible();
  expect(screen.getByRole("tab", { name: "状态" })).toBeVisible();
  expect(screen.getByRole("tab", { name: "参数" })).toBeVisible();
});

it("uses one dominant simulation region and prevents desktop overflow", () => {
  renderWithProviders(<WorkbenchPage />);
  expect(screen.getByTestId("workbench-page")).toHaveClass("lg:overflow-hidden");
  expect(screen.getByTestId("workbench-regions")).toHaveClass("min-w-0", "flex-1");
  expect(screen.getByRole("status")).toBeVisible();
});
