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

it("uses the application shell in the app workspace", () => {
  const router = createMemoryRouter(appRoutes, { initialEntries: ["/app"] });
  renderWithProviders(<RouterProvider router={router} />);

  expect(screen.getByRole("navigation", { name: "主导航" })).toBeVisible();
  expect(screen.getByRole("heading", { name: "我的推演" })).toBeVisible();
});

it("navigates from the shell to an implemented business route", async () => {
  const router = createMemoryRouter(appRoutes, { initialEntries: ["/app"] });
  renderWithProviders(<RouterProvider router={router} />);

  // 侧边栏中的 "新建推演" 链接（第一个匹配的元素）
  const newProjectLinks = screen.getAllByRole("link", { name: "新建推演" });
  const sidebarLink = newProjectLinks.find(
    (el) => el.getAttribute("href") === "/app/new",
  )!;
  await userEvent.click(sidebarLink);

  expect(screen.getByRole("heading", { name: "新建推演" })).toBeVisible();
  expect(
    within(screen.getByRole("navigation", { name: "breadcrumb" })).getByText(
      "新建推演",
    ),
  ).toBeVisible();
});

it("keeps mobile navigation targets at least 44 pixels tall", () => {
  const router = createMemoryRouter(appRoutes, { initialEntries: ["/app"] });
  renderWithProviders(<RouterProvider router={router} />);
  const navigation = within(screen.getByRole("navigation", { name: "主导航" }));

  for (const label of ["我的推演", "模板库"]) {
    expect(navigation.getByRole("link", { name: label })).toHaveClass("min-h-11");
  }
  expect(screen.getByRole("link", { name: "EduFlow 工作台" })).toHaveClass(
    "min-h-11",
  );
});

it("does not mark prefix-like 404 paths as active navigation", () => {
  const router = createMemoryRouter(appRoutes, { initialEntries: ["/newer"] });
  renderWithProviders(<RouterProvider router={router} />);

  expect(screen.getByRole("heading", { name: "404" })).toBeVisible();
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
