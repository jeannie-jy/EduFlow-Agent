import { screen } from "@testing-library/react";
import { beforeEach, expect, it } from "vitest";
import { createMemoryRouter, RouterProvider } from "react-router-dom";
import { appRoutes } from "@/app/router";
import { setAuthState } from "@/lib/auth";
import { renderWithProviders } from "@/test/render";

const routes = [
  ["/app", "我的推演"],
  ["/app/project/_new", "选择模块"],
  ["/login", "欢迎回来"],
  ["/register", "创建你的学习空间"],
  ["/explore/dijkstra", "Dijkstra 最短路径交互推演"],
  ["/missing", "404"],
] as const;

beforeEach(() => {
  localStorage.clear();
});

it.each(routes)("renders %s as %s", async (path, heading) => {
  if (path.startsWith("/app")) {
    setAuthState({ isAuthenticated: true, nickname: "Test", email: "test@example.com" });
  }
  const router = createMemoryRouter(appRoutes, { initialEntries: [path] });

  renderWithProviders(<RouterProvider router={router} />);

  expect(
    await screen.findByRole("heading", { name: heading }, { timeout: 3000 }),
  ).toBeVisible();
});

it("redirects signed-out workspace requests to login with an actionable message", async () => {
  const router = createMemoryRouter(appRoutes, {
    initialEntries: ["/app/project/_new?template=Dijkstra"],
  });

  renderWithProviders(<RouterProvider router={router} />);

  expect(await screen.findByRole("heading", { name: "欢迎回来" })).toBeVisible();
  expect(screen.getByRole("alert")).toHaveTextContent("请先登录后再开始推演");
  expect(router.state.location.pathname).toBe("/login");
  expect(new URLSearchParams(router.state.location.search).get("next")).toBe(
    "/app/project/_new?template=Dijkstra",
  );
});
