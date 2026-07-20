/**
 * 工作台（Dashboard）— 组件测试
 *
 * 测试项目列表渲染、加载/空/错误状态、状态筛选、分页。
 */

import { describe, expect, it, afterEach } from "vitest";
import { screen, waitFor } from "@testing-library/react";
import { http, HttpResponse } from "msw";
import { server } from "@/test/mocks/handlers";
import { renderPage } from "@/test/render";
import { Dashboard } from "@/pages/Dashboard";

describe("Dashboard page", () => {
  afterEach(() => {
    server.resetHandlers();
  });

  it("renders the dashboard header", async () => {
    renderPage(<Dashboard />);

    await waitFor(() => {
      expect(screen.getByText("我的推演")).toBeInTheDocument();
      expect(screen.getByText("管理和创建你的教学推演项目")).toBeInTheDocument();
    });
  });

  it("has a create new project button", async () => {
    renderPage(<Dashboard />);

    await waitFor(() => {
      const newBtn = screen.getByRole("link", { name: /新建推演/ });
      expect(newBtn).toHaveAttribute("href", "/app/new");
    });
  });

  it("renders project cards after loading", async () => {
    renderPage(<Dashboard />);

    await waitFor(() => {
      expect(screen.getByText("Dijkstra 最短路径")).toBeInTheDocument();
      expect(screen.getByText("冒泡排序可视化")).toBeInTheDocument();
    });
  });

  it("shows status badges on project cards", async () => {
    renderPage(<Dashboard />);

    await waitFor(() => {
      expect(screen.getByText("已完成")).toBeInTheDocument();
      expect(screen.getByText("草稿")).toBeInTheDocument();
    });
  });

  it("shows loading skeleton initially", () => {
    renderPage(<Dashboard />);

    // 骨架屏在加载时显示
    const skeletons = document.querySelectorAll('[data-slot="skeleton"]');
    expect(skeletons.length).toBeGreaterThan(0);
  });

  it("shows error state on server error", async () => {
    server.use(
      http.get("http://localhost:8000/api/projects", () => {
        return HttpResponse.json(
          { error: { code: "SERVER_ERROR", message: "Internal server error" } },
          { status: 500 },
        );
      }),
    );

    renderPage(<Dashboard />);

    await waitFor(() => {
      expect(screen.getByText(/服务器错误/)).toBeInTheDocument();
    });
  });

  it("shows error state on network failure", async () => {
    server.use(
      http.get("http://localhost:8000/api/projects", () => {
        return HttpResponse.error();
      }),
    );

    renderPage(<Dashboard />);

    await waitFor(() => {
      expect(screen.getByText(/无法连接到服务器/)).toBeInTheDocument();
    });
  });

  it("has retry button on error state", async () => {
    server.use(
      http.get("http://localhost:8000/api/projects", () => {
        return HttpResponse.error();
      }),
    );

    renderPage(<Dashboard />);

    await waitFor(() => {
      expect(screen.getByRole("button", { name: /重试/ })).toBeInTheDocument();
    });
  });

  it("shows empty state when no projects", async () => {
    server.use(
      http.get("http://localhost:8000/api/projects", () => {
        return HttpResponse.json({
          items: [],
          total: 0,
          page: 1,
          page_size: 20,
        });
      }),
    );

    renderPage(<Dashboard />);

    await waitFor(() => {
      expect(screen.getByText("还没有推演项目")).toBeInTheDocument();
      expect(screen.getByRole("link", { name: /创建第一个推演/ })).toBeInTheDocument();
    });
  });

  it("has status filter buttons", async () => {
    renderPage(<Dashboard />);

    await waitFor(() => {
      expect(screen.getByRole("button", { name: "全部" })).toBeInTheDocument();
      expect(screen.getByRole("button", { name: "草稿" })).toBeInTheDocument();
      expect(screen.getByRole("button", { name: "已完成" })).toBeInTheDocument();
    });
  });

  it("shows project metadata on cards", async () => {
    renderPage(<Dashboard />);

    await waitFor(() => {
      expect(screen.getByText("图算法")).toBeInTheDocument();
      expect(screen.getByText("14 帧")).toBeInTheDocument();
    });
  });
});