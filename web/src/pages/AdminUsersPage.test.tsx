import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { createMemoryRouter, RouterProvider } from "react-router-dom";
import { http, HttpResponse } from "msw";
import { appRoutes } from "@/app/router";
import { setAuthState } from "@/lib/auth";
import { renderWithProviders } from "@/test/render";
import { server } from "@/test/mocks/handlers";

const admin = {
  id: "11111111-1111-1111-1111-111111111111",
  email: "admin@example.com",
  nickname: "Admin",
  role: "admin" as const,
  is_active: true,
  session_count: 1,
  created_at: "2026-01-01T00:00:00Z",
};

const teacher = {
  id: "22222222-2222-2222-2222-222222222222",
  email: "teacher@example.com",
  nickname: "Teacher",
  role: "teacher" as const,
  is_active: true,
  session_count: 2,
  created_at: "2026-01-02T00:00:00Z",
};

beforeEach(() => {
  localStorage.clear();
});

it("hides the admin route from a non-admin cached identity", async () => {
  setAuthState({ isAuthenticated: true, email: teacher.email, nickname: teacher.nickname, role: "teacher" });
  const router = createMemoryRouter(appRoutes, { initialEntries: ["/app/admin/users"] });
  renderWithProviders(<RouterProvider router={router} />);

  expect(await screen.findByRole("heading", { name: "我的推演" })).toBeVisible();
  expect(screen.queryByRole("heading", { name: /用户与权限/ })).not.toBeInTheDocument();
});

it("lists users, prevents self-demotion, changes roles, and revokes sessions", async () => {
  let updatedRole = "teacher";
  let revoked = false;
  setAuthState({ id: admin.id, isAuthenticated: true, email: admin.email, nickname: admin.nickname, role: "admin" });
  server.use(
    http.get("http://localhost:8000/api/admin/users", () => HttpResponse.json({
      users: [admin, { ...teacher, role: updatedRole, session_count: revoked ? 0 : 2 }],
      next_cursor: null,
    })),
    http.patch("http://localhost:8000/api/admin/users/:id", async ({ request }) => {
      const body = await request.json() as { role: string };
      updatedRole = body.role;
      return HttpResponse.json({ ...teacher, role: updatedRole, session_count: 0 });
    }),
    http.delete("http://localhost:8000/api/admin/users/:id/sessions", () => {
      revoked = true;
      return HttpResponse.json({ revoked: 2 });
    }),
  );

  const router = createMemoryRouter(appRoutes, { initialEntries: ["/app/admin/users"] });
  renderWithProviders(<RouterProvider router={router} />);

  expect(await screen.findByRole("heading", { name: /用户与权限/ })).toBeVisible();
  expect(await screen.findByLabelText(`修改 ${admin.email} 的角色`)).toBeDisabled();
  await userEvent.click((await screen.findAllByRole("button", { name: "撤销会话" }))[1]);
  expect(await screen.findByText("已撤销 2 个会话")).toBeVisible();
  await userEvent.selectOptions(screen.getByLabelText(`修改 ${teacher.email} 的角色`), "student");
  await waitFor(() => expect(updatedRole).toBe("student"));
  expect(await screen.findByText("用户权限已更新，原有登录会话已失效")).toBeVisible();
});
