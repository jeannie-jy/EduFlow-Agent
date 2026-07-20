/**
 * 新建推演页 — 组件测试
 *
 * 测试表单渲染、验证、提交、错误处理。
 */

import { describe, expect, it, afterEach } from "vitest";
import { screen, fireEvent, waitFor } from "@testing-library/react";
import { http, HttpResponse } from "msw";
import { server } from "@/test/mocks/handlers";
import { renderPage } from "@/test/render";
import { NewProject } from "@/pages/NewProject";

describe("NewProject page", () => {
  afterEach(() => {
    server.resetHandlers();
  });

  it("renders the creation form", () => {
    renderPage(<NewProject />);

    expect(screen.getByText("新建推演")).toBeInTheDocument();
    expect(screen.getByLabelText("推演标题 *")).toBeInTheDocument();
    expect(screen.getByPlaceholderText("描述你想讲解的知识点内容、重点和注意事项...")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /开始生成教学计划/ })).toBeInTheDocument();
  });

  it("has a back link to dashboard", () => {
    renderPage(<NewProject />);

    const backLink = screen.getByRole("link", { name: /返回工作台/ });
    expect(backLink).toHaveAttribute("href", "/app");
  });

  it("disables submit button when title is empty", () => {
    renderPage(<NewProject />);

    const submitBtn = screen.getByRole("button", { name: /开始生成教学计划/ });
    expect(submitBtn).toBeDisabled();
  });

  it("enables submit button when title is filled", async () => {
    renderPage(<NewProject />);

    const titleInput = screen.getByLabelText("推演标题 *");
    fireEvent.change(titleInput, { target: { value: "Dijkstra 算法" } });

    await waitFor(() => {
      const submitBtn = screen.getByRole("button", { name: /开始生成教学计划/ });
      expect(submitBtn).not.toBeDisabled();
    });
  });

  it("shows submitting state when form is submitted", async () => {
    // 使用延迟响应模拟网络延迟
    server.use(
      http.post("http://localhost:8000/api/projects", async () => {
        await new Promise((r) => setTimeout(r, 500));
        return HttpResponse.json(
          { id: "new-001", title: "test", status: "draft", created_at: "2024-01-01" },
          { status: 201 },
        );
      }),
    );

    renderPage(<NewProject />);

    fireEvent.change(screen.getByLabelText("推演标题 *"), {
      target: { value: "Dijkstra 算法" },
    });
    fireEvent.click(screen.getByRole("button", { name: /开始生成教学计划/ }));

    await waitFor(() => {
      expect(screen.getByRole("button", { name: /正在创建/ })).toBeInTheDocument();
    });
  });

  it("shows error message on server error", async () => {
    server.use(
      http.post("http://localhost:8000/api/projects", () => {
        return HttpResponse.json(
          { error: { code: "VALIDATION_ERROR", message: "标题不能为空" } },
          { status: 422 },
        );
      }),
    );

    renderPage(<NewProject />);

    fireEvent.change(screen.getByLabelText("推演标题 *"), {
      target: { value: "test" },
    });
    fireEvent.click(screen.getByRole("button", { name: /开始生成教学计划/ }));

    await waitFor(() => {
      expect(screen.getByText("创建失败")).toBeInTheDocument();
      expect(screen.getByText("标题不能为空")).toBeInTheDocument();
    });
  });

  it("shows error message on network failure", async () => {
    server.use(
      http.post("http://localhost:8000/api/projects", () => {
        return HttpResponse.error();
      }),
    );

    renderPage(<NewProject />);

    fireEvent.change(screen.getByLabelText("推演标题 *"), {
      target: { value: "test" },
    });
    fireEvent.click(screen.getByRole("button", { name: /开始生成教学计划/ }));

    await waitFor(() => {
      expect(screen.getByText("创建失败")).toBeInTheDocument();
    });
  });

  it("can change audience and difficulty", async () => {
    renderPage(<NewProject />);

    // 初始值：Select 显示的是原始值（不是中文标签）
    const triggers = screen.getAllByRole("combobox");
    expect(triggers).toHaveLength(2);

    // audience 默认值
    expect(triggers[0]).toHaveTextContent("undergraduate_cs");
    // difficulty 默认值
    expect(triggers[1]).toHaveTextContent("intermediate");
  });

  it("renders all form fields with correct placeholders", () => {
    renderPage(<NewProject />);

    expect(screen.getByPlaceholderText("例如：Dijkstra 最短路径算法")).toBeInTheDocument();
    expect(
      screen.getByPlaceholderText("描述你想讲解的知识点内容、重点和注意事项..."),
    ).toBeInTheDocument();
  });

  it("disables form fields during submission", async () => {
    server.use(
      http.post("http://localhost:8000/api/projects", async () => {
        await new Promise((r) => setTimeout(r, 500));
        return HttpResponse.json(
          { id: "new-001", title: "test", status: "draft", created_at: "2024-01-01" },
          { status: 201 },
        );
      }),
    );

    renderPage(<NewProject />);

    fireEvent.change(screen.getByLabelText("推演标题 *"), {
      target: { value: "Dijkstra" },
    });
    fireEvent.click(screen.getByRole("button", { name: /开始生成教学计划/ }));

    await waitFor(() => {
      expect(screen.getByLabelText("推演标题 *")).toBeDisabled();
      expect(
        screen.getByPlaceholderText("描述你想讲解的知识点内容、重点和注意事项..."),
      ).toBeDisabled();
    });
  });
});