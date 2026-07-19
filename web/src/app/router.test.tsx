import { screen } from "@testing-library/react";
import { createMemoryRouter, RouterProvider } from "react-router-dom";
import { appRoutes } from "@/app/router";
import { renderWithProviders } from "@/test/render";

const routes = [
  ["/", "教学工作台"],
  ["/new", "新建推演"],
  ["/project/demo/plan", "教学计划确认"],
  ["/project/demo/edit", "教师编辑器"],
  ["/project/demo/play", "交互式播放器"],
  ["/project/demo/export", "导出中心"],
  ["/templates", "知识点模板库"],
  ["/missing", "页面未找到"],
] as const;

it.each(routes)("renders %s as %s", (path, heading) => {
  const router = createMemoryRouter(appRoutes, { initialEntries: [path] });

  renderWithProviders(<RouterProvider router={router} />);

  expect(screen.getByRole("heading", { name: heading })).toBeVisible();
});
