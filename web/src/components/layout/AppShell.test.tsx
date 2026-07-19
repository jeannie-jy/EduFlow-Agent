import { screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import {
  createMemoryRouter,
  MemoryRouter,
  RouterProvider,
} from "react-router-dom";
import { vi } from "vitest";
import { renderWithProviders } from "@/test/render";
import { App } from "@/app/App";
import { appRoutes } from "@/app/router";
import { AppShell } from "./AppShell";

it("exposes navigation and changes theme", async () => {
  renderWithProviders(
    <MemoryRouter>
      <AppShell>
        <main>工作区</main>
      </AppShell>
    </MemoryRouter>,
  );

  expect(screen.getByRole("navigation", { name: "主导航" })).toBeVisible();
  await userEvent.click(screen.getByRole("button", { name: /主题/ }));
  await userEvent.click(
    await screen.findByRole("menuitemradio", { name: "深色" }),
  );
  expect(document.documentElement.dataset.theme).toBe("dark");
});

it("uses the application shell in the live app", () => {
  renderWithProviders(<App />);

  expect(screen.getByRole("navigation", { name: "主导航" })).toBeVisible();
  expect(screen.getByRole("heading", { name: "教学工作台" })).toBeVisible();
});

it("navigates from the shell to an implemented business route", async () => {
  window.history.replaceState({}, "", "/");
  renderWithProviders(<App />);

  await userEvent.click(screen.getByRole("link", { name: "新建推演" }));

  expect(screen.getByRole("heading", { name: "新建推演" })).toBeVisible();
  expect(
    within(screen.getByRole("navigation", { name: "breadcrumb" })).getByText(
      "新建推演",
    ),
  ).toBeVisible();
  const newProjectLink = screen
    .getAllByRole("link", { name: "新建推演" })
    .find((element) => element.getAttribute("href") === "/new");
  expect(newProjectLink).toHaveAttribute("aria-current", "page");
});

it("keeps mobile navigation targets at least 44 pixels tall", () => {
  renderWithProviders(<App />);
  const navigation = within(screen.getByRole("navigation", { name: "主导航" }));

  for (const label of ["教学路径", "互动推演", "教师编辑器", "模板库", "导出中心"]) {
    expect(navigation.getByRole("link", { name: label })).toHaveClass("min-h-11");
  }
  expect(screen.getByRole("link", { name: "EduFlow 工作台" })).toHaveClass(
    "min-h-11",
  );
});

it("does not mark prefix-like 404 paths as active navigation", () => {
  const router = createMemoryRouter(appRoutes, { initialEntries: ["/newer"] });
  renderWithProviders(<RouterProvider router={router} />);

  expect(screen.getByRole("heading", { name: "页面未找到" })).toBeVisible();
  expect(screen.getByRole("link", { name: "新建推演" })).not.toHaveAttribute(
    "aria-current",
  );
});

it("composes sidebar route links without button-semantic warnings", () => {
  const consoleError = vi.spyOn(console, "error").mockImplementation(() => undefined);

  try {
    renderWithProviders(<App />);
    const messages = consoleError.mock.calls.flat().join(" ");
    expect(messages).not.toContain("nativeButton");
  } finally {
    consoleError.mockRestore();
  }
});
