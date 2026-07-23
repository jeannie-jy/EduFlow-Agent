/**
 * 项目服务 — 单元测试
 */

import { describe, expect, it, vi, afterEach } from "vitest";
import { createProject, listProjects, getProject, deleteProject } from "@/services/projects";

describe("projects service", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("createProject sends correct POST request", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({
        ok: true, status: 201,
        json: () => Promise.resolve({ id: "abc", title: "测试", status: "draft", created_at: "2024-01-01" }),
      }),
    );

    const result = await createProject({
      title: "Dijkstra 最短路径",
      input_type: "natural_language",
      input_content: "讲解 Dijkstra 算法",
      audience: "undergraduate_cs",
      difficulty: "intermediate",
    });

    expect(result.id).toBe("abc");
    expect(result.title).toBe("测试");
    expect(result.status).toBe("draft");
  });

  it("listProjects sends correct GET request", async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true, status: 200,
      json: () => Promise.resolve({
        items: [{ id: "1", title: "项目1", status: "draft", topic: null, difficulty: "intermediate", frame_count: 0, updated_at: "2024-01-01" }],
        total: 1, page: 1, page_size: 20,
      }),
    });
    vi.stubGlobal("fetch", fetchMock);

    const result = await listProjects({ page: 1, page_size: 10, status: "draft" });

    expect(result.items).toHaveLength(1);
    expect(result.total).toBe(1);

    const url = fetchMock.mock.calls[0][0] as string;
    expect(url).toContain("page=1");
    expect(url).toContain("page_size=10");
    expect(url).toContain("status=draft");
  });

  it("getProject sends correct GET request", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({
        ok: true, status: 200,
        json: () => Promise.resolve({
          id: "abc", title: "测试项目", status: "done",
          audience: "undergraduate_cs", difficulty: "intermediate",
          teaching_plan: null, knowledge_graph: null,
          dsl: null, quality_report: null, frame_count: 10,
          created_at: "2024-01-01", updated_at: "2024-01-02",
        }),
      }),
    );

    const result = await getProject("abc");

    expect(result.id).toBe("abc");
    expect(result.frame_count).toBe(10);
    expect(result.status).toBe("done");
  });

  it("deleteProject sends correct DELETE request", async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true, status: 204,
      json: () => Promise.reject(new Error("No body")),
    });
    vi.stubGlobal("fetch", fetchMock);

    await deleteProject("abc");

    const options = fetchMock.mock.calls[0][1] as RequestInit;
    expect(options.method).toBe("DELETE");
  });
});