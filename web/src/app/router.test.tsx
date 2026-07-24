import { screen } from "@testing-library/react";
import { createMemoryRouter, RouterProvider } from "react-router-dom";
import { appRoutes } from "@/app/router";
import { renderWithProviders } from "@/test/render";

const routes = [
  ["/app", "我的推演"],
  ["/app/new", "新建推演"],
  ["/login", "欢迎回来"],
  ["/register", "创建你的学习空间"],
  ["/explore/dijkstra", "Dijkstra 最短路径交互推演"],
  ["/missing", "404"],
] as const;

it.each(routes)("renders %s as %s", (path, heading) => {
  const router = createMemoryRouter(appRoutes, { initialEntries: [path] });

  renderWithProviders(<RouterProvider router={router} />);

  expect(screen.getByRole("heading", { name: heading })).toBeVisible();
});
