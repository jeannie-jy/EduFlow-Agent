/**
 * ProjectWorkspace 冒烟测试 — 三步流程（select → plan → results）。
 *
 * 覆盖：新建模式（_new）下渲染模块选择步骤；历史项目打开时按状态进入对应步骤。
 */

import { describe, expect, it, afterEach } from "vitest";
import { screen, waitFor, cleanup } from "@testing-library/react";
import { render } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Routes, Route } from "react-router-dom";
import { http, HttpResponse } from "msw";
import { server } from "@/test/mocks/handlers";
import { AppProviders } from "@/app/AppProviders";
import { ProjectWorkspace } from "@/pages/ProjectWorkspace";

const PROJECT_ID = "00000000-0000-0000-0000-000000000001";

/** 渲染工作区：需要路由参数上下文（useParams） */
function renderWorkspace(route: string) {
  return render(
    <MemoryRouter initialEntries={[route]}>
      <AppProviders>
        <Routes>
          <Route path="/app/project/:projectId" element={<ProjectWorkspace />} />
        </Routes>
      </AppProviders>
    </MemoryRouter>,
  );
}

describe("ProjectWorkspace", () => {
  afterEach(() => {
    cleanup();
    server.resetHandlers();
  });

  it("renders module selection step in new-project mode", async () => {
    renderWorkspace("/app/project/_new");

    await waitFor(() => {
      expect(screen.getByText("输入教学主题")).toBeInTheDocument();
      expect(screen.getByText("思维导图")).toBeInTheDocument();
      expect(screen.getByRole("button", { name: "上传课件" })).toBeInTheDocument();
    });
    for (const moduleName of ["思维导图", "知识卡片", "交互推演", "小练习", "对比分析", "教学视频", "常见误区", "学习路径", "代码沙箱"]) {
      expect(screen.getByText(moduleName)).toBeInTheDocument();
    }
  });

  it("offers explicit teacher indexing and blocks strict mode without consent", async () => {
    const user = userEvent.setup();
    const calls: string[] = [];
    server.use(
      http.get("http://localhost:8000/api/materials", () => HttpResponse.json({
        items: [{ id: "mat-1", filename: "lesson.md", type: "md", size_bytes: 100,
                  status: "parsed", is_library: false }],
      })),
      http.get("http://localhost:8000/api/materials/library", () => HttpResponse.json({ items: [] })),
      http.post("http://localhost:8000/api/materials/:id/library", () => {
        calls.push("enabled");
        return HttpResponse.json({ material_id: "mat-1", source_id: "source-1" });
      }),
      http.post("http://localhost:8000/api/materials/:id/index", () => {
        calls.push("indexed");
        return HttpResponse.json({ id: "mat-1", status: "completed", job_id: "job-1" });
      }),
    );
    renderWorkspace("/app/project/_new");
    await user.click(await screen.findByRole("button", { name: "加入资料库并索引" }));
    await waitFor(() => expect(calls).toEqual(["enabled", "indexed"]));
    await user.click(screen.getByLabelText(/仅依据本项目选入的教师资料生成/));
    await user.click(screen.getByRole("button", { name: /开始生成/ }));
    expect(await screen.findByText(/仅依据指定资料需要授权模型处理/)).toBeInTheDocument();
  });

  it("attaches a selected indexed source before strict project generation", async () => {
    const user = userEvent.setup();
    const calls: string[] = [];
    const materialId = "00000000-0000-0000-0000-000000000011";
    server.use(
      http.get("http://localhost:8000/api/materials", () => HttpResponse.json({
        items: [{ id: materialId, filename: "lecture.pdf", type: "pdf", size_bytes: 300,
                  status: "parsed", is_library: true }],
      })),
      http.get("http://localhost:8000/api/materials/library", () => HttpResponse.json({
        items: [{ id: materialId, filename: "lecture.pdf", parse_status: "parsed",
                  index_status: "published", job_status: "completed", index_error: null, size_bytes: 300 }],
      })),
      http.post("http://localhost:8000/api/me/consents", () => HttpResponse.json({ accepted: true })),
      http.put("http://localhost:8000/api/materials/:id/projects/:projectId", () => {
        calls.push("attach");
        return HttpResponse.json({ material_id: materialId, source_id: "source-1" });
      }),
      http.post("http://localhost:8000/api/projects/:id/generate", async ({ request }) => {
        const body = await request.json() as { constraints?: Record<string, unknown> };
        calls.push(`generate:${String(body.constraints?.knowledge_scope)}`);
        expect(body.constraints?.material_ids).toEqual([]);
        return HttpResponse.json({ stream_url: "/api/projects/new-proj-001/generate/stream" }, { status: 202 });
      }),
      http.get("*/api/projects/new-proj-001/generate/stream", () => new HttpResponse(
        new ReadableStream({ start(controller) { controller.close(); } }),
        { headers: { "Content-Type": "text/event-stream" } },
      )),
    );
    renderWorkspace("/app/project/_new");
    await user.click(await screen.findByLabelText(/选入教师资料库检索/));
    await user.click(screen.getByLabelText(/仅依据本项目选入的教师资料生成/));
    await user.click(screen.getByLabelText(/允许将本项目选入的课件片段发送给模型/));
    await user.type(screen.getByPlaceholderText("例如：Dijkstra 最短路径算法的工作原理和正确性证明"), "排序算法");
    await user.click(screen.getByRole("button", { name: /开始生成/ }));
    await waitFor(() => expect(calls).toEqual(["attach", "generate:selected_materials"]));
  });

  it("renders results step for a completed project", async () => {
    renderWorkspace(`/app/project/${PROJECT_ID}`);

    // 完成状态是步骤导航的唯一事实来源。即使旧项目没有持久化
    // module_outputs，也应进入成果页并展示明确的空状态。
    await waitFor(() => {
      expect(screen.getByText("成果预览")).toBeInTheDocument();
      expect(screen.getByRole("heading", { name: "尚未生成模块产物" })).toBeInTheDocument();
    });
    expect(screen.queryByRole("heading", { name: "选择模块" })).not.toBeInTheDocument();
  });

  it("restores a persisted waiting-for-approval state after refresh", async () => {
    server.use(http.get("http://localhost:8000/api/projects/:id", ({ params }) => HttpResponse.json({
      id: params.id,
      title: "Dijkstra 最短路径",
      status: "planning",
      teaching_plan: { objectives: ["理解最短路径"], outline: [] },
      module_outputs: {},
      selected_modules: [],
      dsl: { frames: [] },
      updated_at: "2026-09-05T00:00:00Z",
    })));

    renderWorkspace(`/app/project/${PROJECT_ID}`);

    await waitFor(() => {
      expect(screen.getByRole("heading", { name: "确认教学计划" })).toBeInTheDocument();
    });
  });

  it("cancels and deletes an abandoned new project before returning to selection", async () => {
    const user = userEvent.setup();
    const requests: string[] = [];
    const encoder = new TextEncoder();
    const stream = new ReadableStream({
      start(controller) {
        controller.enqueue(encoder.encode(
          'event: progress\ndata: {"phase":"planning","pct":10,"message":"正在规划"}\n\n',
        ));
      },
    });
    server.use(
      http.get("*/api/projects/new-proj-001/generate/stream", () => new HttpResponse(stream, {
        headers: { "Content-Type": "text/event-stream" },
      })),
      http.delete("http://localhost:8000/api/projects/:id/generate", ({ params }) => {
        requests.push(`cancel:${String(params.id)}`);
        return HttpResponse.json({ project_id: params.id, status: "cancelled" });
      }),
      http.delete("http://localhost:8000/api/projects/:id", ({ params }) => {
        requests.push(`delete:${String(params.id)}`);
        return new HttpResponse(null, { status: 204 });
      }),
      http.post("http://localhost:8000/api/projects/:id/generate", ({ params }) => HttpResponse.json({
        stream_url: `/api/projects/${String(params.id)}/generate/stream`,
      }, { status: 202 })),
    );

    renderWorkspace("/app/project/_new");
    await user.type(await screen.findByPlaceholderText("例如：Dijkstra 最短路径算法"), "可取消的 BFS");
    await user.click(await screen.findByRole("button", { name: /开始生成/ }));
    await user.click(await screen.findByRole("button", { name: "取消" }));

    await waitFor(() => {
      expect(requests).toEqual([
        "cancel:new-proj-001",
        "delete:new-proj-001",
      ]);
      expect(window.sessionStorage.getItem("eduflow:active-stream:new-proj-001")).toBeNull();
      expect(screen.getByRole("heading", { level: 2, name: "选择模块" })).toBeInTheDocument();
    });
  });
});
