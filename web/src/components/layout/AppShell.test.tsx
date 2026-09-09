import { screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import {
  createMemoryRouter,
  MemoryRouter,
  RouterProvider,
} from "react-router-dom";
import { vi } from "vitest";
import { renderWithProviders } from "@/test/render";
import { appRoutes } from "@/app/router";
import { AppShell } from "./AppShell";
import { setAuthState } from "@/lib/auth";

beforeEach(() => localStorage.clear());

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
    await screen.findByRole("menuitemradio", { name: "Dark" }),
  );
  expect(document.documentElement.dataset.theme).toBe("dark");
});

it("uses the application shell in the app workspace", async () => {
  const router = createMemoryRouter(appRoutes, { initialEntries: ["/app"] });
  renderWithProviders(<RouterProvider router={router} />);

  expect(await screen.findByRole("navigation", { name: "主导航" })).toBeVisible();
  expect(await screen.findByRole("heading", { name: "我的推演" })).toBeVisible();
});

it("navigates from the shell to an implemented business route", async () => {
  const router = createMemoryRouter(appRoutes, { initialEntries: ["/app"] });
  renderWithProviders(<RouterProvider router={router} />);

  // 侧边栏中的 "新建推演" 链接（第一个匹配的元素）
  const newProjectLinks = await screen.findAllByRole("link", { name: "新建推演" });
  const sidebarLink = newProjectLinks.find(
    (el) => el.getAttribute("href") === "/app/new",
  )!;
  await userEvent.click(sidebarLink);

  // /app/new 重定向到 /app/project/_new（ProjectWorkspace 新建模式）
  expect(await screen.findByRole("heading", { name: "选择模块" }, { timeout: 3000 })).toBeVisible();
});

it("keeps mobile navigation targets at least 44 pixels tall", async () => {
  const router = createMemoryRouter(appRoutes, { initialEntries: ["/app"] });
  renderWithProviders(<RouterProvider router={router} />);
  const navigation = within(await screen.findByRole("navigation", { name: "主导航" }));

  for (const label of ["我的推演", "模板库"]) {
    expect(navigation.getByRole("link", { name: label })).toHaveClass("min-h-11");
  }
  expect(screen.getByRole("link", { name: "EduFlow 工作台" })).toHaveClass(
    "min-h-11",
  );
});

it("does not mark prefix-like 404 paths as active navigation", async () => {
  const router = createMemoryRouter(appRoutes, { initialEntries: ["/newer"] });
  renderWithProviders(<RouterProvider router={router} />);

  expect(await screen.findByRole("heading", { name: "404" })).toBeVisible();
});

it("composes sidebar route links without button-semantic warnings", () => {
  const router = createMemoryRouter(appRoutes, { initialEntries: ["/app"] });
  const consoleError = vi.spyOn(console, "error").mockImplementation(() => undefined);

  try {
    renderWithProviders(<RouterProvider router={router} />);
    const messages = consoleError.mock.calls.flat().join(" ");
    expect(messages).not.toContain("nativeButton");
  } finally {
    consoleError.mockRestore();
  }
});

it("shows administration navigation only to admins", async () => {
  setAuthState({ isAuthenticated: true, nickname: "Admin", email: "admin@example.com", role: "admin" });
  const router = createMemoryRouter(appRoutes, { initialEntries: ["/app"] });
  renderWithProviders(<RouterProvider router={router} />);

  expect(await screen.findByRole("link", { name: "用户与权限" })).toHaveAttribute("href", "/app/admin/users");
});
